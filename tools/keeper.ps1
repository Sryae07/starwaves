# Sryaestart keeper: ensure backend + tunnel alive, publish tunnel URL to GitHub.
# Runs forever hidden; GitHub Pages reads docs\current-server.json for auto-redirect.
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root '.venv\Scripts\python.exe'
$data = Join-Path $root 'data'
New-Item -ItemType Directory -Force -Path $data | Out-Null
$cf = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'
if (-not (Test-Path -LiteralPath $cf)) { $cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source }
$pointer = Join-Path $root 'docs\current-server.json'
$stampLog = Join-Path $data 'autostart.log'

function Start-Backend {
    $used = netstat -ano | Select-String ':8000' | Select-String 'LISTENING'
    if (-not $used) {
        Start-Process -WindowStyle Hidden -FilePath $py -ArgumentList '-m','uvicorn','app.main:app','--host','0.0.0.0','--port','8000' -WorkingDirectory $root
        Add-Content -LiteralPath $stampLog -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' backend started') -Encoding UTF8
    }
}

function Start-Tunnel {
    if (-not $cf) { return }
    if (Get-Process cloudflared -ErrorAction SilentlyContinue) { return }
    $log = Join-Path $data 'tunnel.log'
    $err = Join-Path $data 'tunnel.err.log'
    Start-Process -WindowStyle Hidden -FilePath $cf -ArgumentList 'tunnel','--url','http://127.0.0.1:8000','--no-autoupdate' -RedirectStandardOutput $log -RedirectStandardError $err
    $url = $null
    for ($i = 0; $i -lt 20 -and -not $url; $i++) {
        Start-Sleep -Seconds 2
        $url = Select-String -Path $log, $err -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -ErrorAction SilentlyContinue | Select-Object -First 1 | ForEach-Object { $_.Matches[0].Value }
    }
    if ($url) {
        Set-Content -LiteralPath (Join-Path $data 'tunnel_url.txt') -Value $url -Encoding UTF8
        Publish-Pointer $url
    }
    Add-Content -LiteralPath $stampLog -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' tunnel started') -Encoding UTF8
}

function Publish-Pointer($url) {
    $current = if (Test-Path -LiteralPath $pointer) { (Get-Content -LiteralPath $pointer -Raw).Trim() } else { '' }
    $json = '{"url":"' + $url + '"}'
    if ($current -eq $json) { return }
    Set-Content -LiteralPath $pointer -Value $json -Encoding UTF8
    for ($i = 0; $i -lt 6; $i++) {
        git -C $root add docs/current-server.json 2>$null
        git -C $root -c user.name=Sryaestart -c user.email=sryaestart@localhost commit -m 'auto: update tunnel url' --only docs/current-server.json 2>$null
        git -C $root push origin main 2>$null
        if ($LASTEXITCODE -eq 0) {
            Add-Content -LiteralPath $stampLog -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' pointer published ' + $url) -Encoding UTF8
            return
        }
        Start-Sleep -Seconds 20
    }
}

while ($true) {
    Start-Backend
    Start-Tunnel
    Start-Sleep -Seconds 300
}
