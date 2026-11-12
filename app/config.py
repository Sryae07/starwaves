"""集中配置：全部从环境变量 / .env 读取，敏感信息不进仓库。"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'data' / 'starwaves.db').as_posix()}")
API_KEY = os.getenv("API_KEY", "").strip() or None
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "").strip()
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
STATIC_DIR = BASE_DIR / "app" / "static"

# 米游社（非官方）同步配置
HKRPG_COOKIE = os.getenv("HKRPG_COOKIE", "").strip()
HKRPG_SERVER = os.getenv("HKRPG_SERVER", "cn").strip()
HKRPG_UID = os.getenv("HKRPG_UID", "").strip()

# 游戏规则、启动路径、资讯源等按游戏维度的配置已收敛到 app/games.py 注册表，
# 新增游戏时无需再改动本文件（启动路径的环境变量覆盖仍按 GameSpec.launch_env_key 读取）。
