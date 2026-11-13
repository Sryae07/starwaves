# Sryaestart keeper v2: backend + tunnel health management, publish tunnel URL to GitHub.
# Runs forever hidden; GitHub Pages reads docs\current-server.json for auto-redirect.
$createdNew = $false
$mutex = New-Object System.Threading.Mutex($true, 'Global\SryaestartKeeper', [ref]$createdNew)
if (-not $createdNew) { exit }
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$root = Split-Path -Parent $PSScriptRoot
$dashRepo = Join-Path (Split-Path -Parent $root) 'sryaestart'
$py = Join-Path $root '.venv\Scripts\python.exe'
$data = Join-Path $root 'data'
New-Item -ItemType Directory -Force -Path $data | Out-Null
$cf = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'
if (-not (Test-Path -LiteralPath $cf)) { $cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source }
$pointer = Join-Path $root 'docs\current-server.json'
$stampLog = Join-Path $data 'autostart.log'
$tunnelUrlFile = Join-Path $data 'tunnel_url.txt'

function Log($msg) {
    Add-Content -LiteralPath $stampLog -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $msg) -Encoding UTF8
}

function Test-Http($url, $timeoutMs = 8000) {
    try {
        $req = [System.Net.HttpWebRequest]::Create($url)
        $req.Timeout = $timeoutMs
        $req.UserAgent = 'sryaestart-keeper'
        $resp = $req.GetResponse()
        $ok = ($resp.StatusCode -eq 200)
        $resp.Close()
        return $ok
    } catch { return $false }
}

function Get-KnownTunnelUrl {
    if (Test-Path -LiteralPath $tunnelUrlFile) {
        $u = (Get-Content -LiteralPath $tunnelUrlFile -Raw -Encoding UTF8).Trim()
        if ($u -match '^https://[a-z0-9-]+\.trycloudflare\.com$') { return $u }
    }
    return $null
}

function Stop-Tunnels {
    $procs = Get-Process cloudflared -ErrorAction SilentlyContinue
    if ($procs) {
        $procs | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
}

function Start-Backend {
    $used = netstat -ano | Select-String ':8000' | Select-String 'LISTENING'
    if (-not $used) {
        Start-Process -WindowStyle Hidden -FilePath $py -ArgumentList '-m','uvicorn','app.main:app','--host','0.0.0.0','--port','8000' -WorkingDirectory $root
        Log 'backend started'
    }
}

function Start-Tunnel {
    if (-not $cf) { Log 'cloudflared not found'; return }
    $known = Get-KnownTunnelUrl
    if ($known) {
        if (Test-Http ($known + '/api/games')) {
            Publish-Pointer $known
            return
        }
        Log ('tunnel dead, restarting: ' + $known)
        Stop-Tunnels
    } else {
        Stop-Tunnels
    }
    $log = Join-Path $data 'tunnel.log'
    $err = Join-Path $data 'tunnel.err.log'
    Remove-Item $log, $err -ErrorAction SilentlyContinue
    Start-Process -WindowStyle Hidden -FilePath $cf -ArgumentList 'tunnel','--url','http://127.0.0.1:8000','--no-autoupdate' -WorkingDirectory $root -RedirectStandardOutput $log -RedirectStandardError $err
    $url = $null
    for ($i = 0; $i -lt 25 -and -not $url; $i++) {
        Start-Sleep -Seconds 2
        $url = Select-String -Path $log, $err -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -ErrorAction SilentlyContinue | Select-Object -First 1 | ForEach-Object { $_.Matches[0].Value }
    }
    if ($url) {
        Set-Content -LiteralPath $tunnelUrlFile -Value $url -Encoding UTF8
        for ($i = 0; $i -lt 10; $i++) {
            if (Test-Http ($url + '/api/games')) { break }
            Start-Sleep -Seconds 3
        }
        Publish-Pointer $url
        Log ('tunnel started ' + $url)
    } else {
        Log 'tunnel start failed: no url in logs'
    }
}

function Publish-Pointer($url) {
    $json = '{"url":"' + $url + '"}'
    $targets = @(
        @{ repo = $root; file = 'docs/current-server.json' },
        @{ repo = $dashRepo; file = 'current-server.json' }
    )
    foreach ($t in $targets) {
        $pf = Join-Path $t.repo $t.file
        if (-not (Test-Path -LiteralPath $pf)) { continue }
        $current = (Get-Content -LiteralPath $pf -Raw).Trim()
        if ($current -eq $json) { continue }
        Set-Content -LiteralPath $pf -Value $json -Encoding UTF8
        for ($i = 0; $i -lt 6; $i++) {
            git -C $t.repo pull --rebase origin main 2>$null
            git -C $t.repo add $t.file 2>$null
            git -C $t.repo -c user.name=Sryaestart -c user.email=sryaestart@localhost commit -m 'auto: update tunnel url' --only $t.file 2>$null
            git -C $t.repo push origin main 2>$null
            if ($LASTEXITCODE -eq 0) {
                Log ('pointer published ' + $url + ' -> ' + $t.file)
                break
            }
            Start-Sleep -Seconds 20
        }
    }
}

while ($true) {
    try {
        Start-Backend
        Start-Tunnel
    } catch {
        Log ('keeper error: ' + $_.Exception.Message)
    }
    Start-Sleep -Seconds 120
}
