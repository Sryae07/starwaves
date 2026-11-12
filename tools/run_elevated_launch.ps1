# Elevated launch helper: called by scheduled task StarWavesLaunchGame (highest privileges).
$root = Split-Path -Parent $PSScriptRoot
$targetFile = Join-Path $root 'data\launch_target.txt'
$log = Join-Path $root 'data\launch.log'
if (-not (Test-Path -LiteralPath $targetFile)) { exit 0 }
$lines = ([IO.File]::ReadAllText($targetFile, [Text.Encoding]::UTF8)).Trim() -split "`r?`n"
$target = $lines[0].Trim()
$extraArgs = if ($lines.Count -gt 1) { $lines[1].Trim() } else { '' }
Remove-Item -LiteralPath $targetFile -Force -ErrorAction SilentlyContinue
if (-not $target) { exit 0 }
$elev = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Add-Content -LiteralPath $log -Value ("{0} launching {1} elevated={2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $target, $elev) -Encoding UTF8
try {
    if ($target -like '*.ps1') {
        Start-Process -FilePath "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',('"{0}"' -f $target) -WorkingDirectory (Split-Path -Parent $target)
    } elseif ($extraArgs) {
        Start-Process -FilePath $target -ArgumentList $extraArgs -WorkingDirectory (Split-Path -Parent $target)
    } else {
        Start-Process -FilePath $target -WorkingDirectory (Split-Path -Parent $target)
    }
} catch {
    Add-Content -LiteralPath $log -Value ("ERROR: {0}" -f $_.Exception.Message) -Encoding UTF8
}
