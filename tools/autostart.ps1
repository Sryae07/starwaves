# Sryaestart autostart: backend (port 8000) + public tunnel, idempotent.
# Latest public URL is written to data\tunnel_url.txt; log in data\autostart.log
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root '.venv\Scripts\python.exe'
$data = Join-Path $root 'data'
New-Item -ItemType Directory -Force -Path $data | Out-Null
$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

$portUsed = netstat -ano | Select-String ':8000' | Select-String 'LISTENING'
if (-not $portUsed) {
    Start-Process -WindowStyle Hidden -FilePath $py -ArgumentList '-m','uvicorn','app.main:app','--host','0.0.0.0','--port','8000' -WorkingDirectory $root
    Add-Content -LiteralPath (Join-Path $data 'autostart.log') -Value ($stamp + ' backend started') -Encoding UTF8
}

$cfRunning = Get-Process cloudflared -ErrorAction SilentlyContinue
if (-not $cfRunning) {
    $cf = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'
    if (-not (Test-Path -LiteralPath $cf)) { $cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source }
    if ($cf -and (Test-Path -LiteralPath $cf)) {
        $log = Join-Path $data 'tunnel.log'
        $err = Join-Path $data 'tunnel.err.log'
        Start-Process -WindowStyle Hidden -FilePath $cf -ArgumentList 'tunnel','--url','http://127.0.0.1:8000','--no-autoupdate' -RedirectStandardOutput $log -RedirectStandardError $err
        $url = $null
        for ($i = 0; $i -lt 20 -and -not $url; $i++) {
            Start-Sleep -Seconds 2
            $url = Select-String -Path $log, $err -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -ErrorAction SilentlyContinue | Select-Object -First 1 | ForEach-Object { $_.Matches[0].Value }
        }
        if ($url) { Set-Content -LiteralPath (Join-Path $data 'tunnel_url.txt') -Value $url -Encoding UTF8 }
        Add-Content -LiteralPath (Join-Path $data 'autostart.log') -Value ($stamp + ' tunnel started') -Encoding UTF8
    }
}
