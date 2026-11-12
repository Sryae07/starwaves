@echo off
cd /d "%~dp0"
set "SW_ROOT=%~dp0"
echo [StarWaves] One-time setup: a UAC prompt will appear. Click Yes.
powershell -NoProfile -Command "$c=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes((Get-Content -Raw ($env:SW_ROOT + 'tools\setup_launch_task.ps1')))); Start-Process powershell -Verb RunAs -WindowStyle Hidden -ArgumentList '-NoProfile','-EncodedCommand',$c"
echo [StarWaves] Once approved, task StarWavesLaunchGame is active and phone launch will work without prompts.
pause
