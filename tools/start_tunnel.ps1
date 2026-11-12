# 一键创建 Cloudflare 快速隧道：把本机看板映射到公网（电脑需保持开机）
# 地址每次重启会变化，最新地址写入 data\tunnel_url.txt
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$cf = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'
if (-not (Test-Path $cf)) { $cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source }
if (-not $cf) {
    Write-Host '[StarWaves] 未找到 cloudflared，请先安装: winget install Cloudflare.cloudflared'
    return
}
$data = Join-Path $root 'data'
New-Item -ItemType Directory -Force -Path $data | Out-Null
$log = Join-Path $data 'tunnel.log'
$err = Join-Path $data 'tunnel.err.log'
$proc = Start-Process -WindowStyle Hidden -FilePath $cf -ArgumentList 'tunnel','--url','http://127.0.0.1:8000','--no-autoupdate' -RedirectStandardOutput $log -RedirectStandardError $err -PassThru
Write-Host '[StarWaves] 正在创建公网隧道，等待地址（约 10 秒）...'
$url = $null
for ($i = 0; $i -lt 15 -and -not $url; $i++) {
    Start-Sleep -Seconds 2
    $url = Select-String -Path $log, $err -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -ErrorAction SilentlyContinue | Select-Object -First 1 | ForEach-Object { $_.Matches[0].Value }
}
if ($url) {
    Set-Content -LiteralPath (Join-Path $data 'tunnel_url.txt') -Value $url -Encoding UTF8
    Write-Host "公网看板地址: $url"
    Write-Host '[StarWaves] 手机在任何网络打开该地址即可进入完整看板（电脑需保持开机）。'
    Start-Process $url
} else {
    Write-Host "[StarWaves] 暂时没读到地址，稍后查看 $log"
}
