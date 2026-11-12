# Elevated launch helper: called by scheduled task StarWavesLaunchGame (highest privileges).
$root = Split-Path -Parent $PSScriptRoot
$targetFile = Join-Path $root 'data\launch_target.txt'
$log = Join-Path $root 'data\launch.log'
if (-not (Test-Path -LiteralPath $targetFile)) { exit 0 }
$target = (Get-Content -LiteralPath $targetFile -Raw).Trim()
Remove-Item -LiteralPath $targetFile -Force -ErrorAction SilentlyContinue
if (-not $target) { exit 0 }
$elev = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Add-Content -LiteralPath $log -Value ("{0} launching {1} elevated={2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $target, $elev) -Encoding UTF8
try {
    Start-Process -FilePath $target
} catch {
    Add-Content -LiteralPath $log -Value ("ERROR: {0}" -f $_.Exception.Message) -Encoding UTF8
}
