"""集中配置：全部从环境变量 / .env 读取，敏感信息不进仓库。"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'data' / 'starwaves.db').as_posix()}")
API_KEY = os.getenv("API_KEY", "").strip() or None
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
STATIC_DIR = BASE_DIR / "app" / "static"

# 米游社（非官方）同步配置
HKRPG_COOKIE = os.getenv("HKRPG_COOKIE", "").strip()
HKRPG_SERVER = os.getenv("HKRPG_SERVER", "cn").strip()
HKRPG_UID = os.getenv("HKRPG_UID", "").strip()

# 启动游戏：留空则按常见安装路径自动探测（仅 Windows 本机部署有效）
LAUNCH_HSR_PATH = os.getenv("LAUNCH_HSR_PATH", "").strip()
LAUNCH_WUWA_PATH = os.getenv("LAUNCH_WUWA_PATH", "").strip()

# 体力恢复规则：每点所需分钟数 / 上限
GAME_RULES = {
    "hsr": {"label": "星穹铁道", "stamina_name": "开拓力", "minutes_per_point": 6, "cap": 240},
    "wuwa": {"label": "鸣潮", "stamina_name": "结晶波片", "minutes_per_point": 6, "cap": 240},
}
