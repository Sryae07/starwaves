# 一次性配置：创建最高权限计划任务 StarWavesLaunchGame，用于免 UAC 提权启动游戏。
# 本脚本必须以管理员身份运行（setup-launch-task.bat 会自动触发 UAC 提升）。
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$helper = Join-Path $root 'tools\run_elevated_launch.ps1'
$ps = "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe"
$tr = '"{0}" -NoProfile -ExecutionPolicy Bypass -File "{1}"' -f $ps, $helper
schtasks /Create /TN "StarWavesLaunchGame" /TR $tr /SC ONCE /ST 23:59 /RL HIGHEST /F
if ($LASTEXITCODE -eq 0) {
    Write-Host "[StarWaves] 创建成功：手机/网页点「启动游戏」将自动以管理员权限启动，不再弹 UAC。"
    $data = Join-Path $root 'data'
    New-Item -ItemType Directory -Force -Path $data | Out-Null
    Set-Content -LiteralPath (Join-Path $data 'launch_task_ok.txt') -Value (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') -Encoding UTF8
} else {
    Write-Host "[StarWaves] 创建失败：请确认已以管理员身份运行本脚本。"
}
Start-Sleep -Seconds 2
