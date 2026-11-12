@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "SW_ROOT=%~dp0"
echo [StarWaves] ???? UAC ????????"?"????????
powershell -NoProfile -Command "$c=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes((Get-Content -Raw ($env:SW_ROOT + 'tools\setup_launch_task.ps1')))); Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-EncodedCommand',$c"
echo [StarWaves] ????????? StarWavesLaunchGame ???????????
pause
