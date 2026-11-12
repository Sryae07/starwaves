# One-time setup: create highest-privilege scheduled task StarWavesLaunchGame.
# Root is taken from SW_ROOT env (when invoked via encoded command) or from script location.
$root = if ($env:SW_ROOT) { $env:SW_ROOT.TrimEnd('\') } elseif ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot } else { '' }
$helper = Join-Path $root 'tools\run_elevated_launch.ps1'
$ps = "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe"
$tr = '"{0}" -NoProfile -ExecutionPolicy Bypass -File "{1}"' -f $ps, $helper
schtasks /Create /TN "StarWavesLaunchGame" /TR $tr /SC ONCE /ST 23:59 /RL HIGHEST /F | Out-Null
if ($LASTEXITCODE -eq 0) {
    $data = Join-Path $root 'data'
    New-Item -ItemType Directory -Force -Path $data | Out-Null
    Set-Content -LiteralPath (Join-Path $data 'launch_task_ok.txt') -Value (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') -Encoding UTF8
} else {
    Set-Content -LiteralPath (Join-Path $root 'data\launch_task_fail.txt') -Value 'schtasks create failed' -Encoding UTF8
}
Start-Sleep -Seconds 1
