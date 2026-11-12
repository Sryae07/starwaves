@echo off
chcp 65001 >nul
title Sryaestart - 游戏启动器
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [Sryaestart] 首次运行：正在创建虚拟环境并安装依赖...
    py -3.12 -m venv .venv 2>nul || python -m venv .venv
    .venv\Scripts\python -m pip install -q -r requirements.txt
)

echo [Sryaestart] 启动服务: http://127.0.0.1:8000
start "" "http://127.0.0.1:8000"
echo [Sryaestart] 局域网/手机访问请用本机 IP:8000（公网访问请运行 start-tunnel.bat）
.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

pause
