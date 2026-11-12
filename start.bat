@echo off
chcp 65001 >nul
title StarWaves - 双游档案
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [StarWaves] 首次运行：正在创建虚拟环境并安装依赖...
    py -3.12 -m venv .venv 2>nul || python -m venv .venv
    .venv\Scripts\python -m pip install -q -r requirements.txt
)

echo [StarWaves] 启动服务: http://127.0.0.1:8000
start "" "http://127.0.0.1:8000"
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

pause
