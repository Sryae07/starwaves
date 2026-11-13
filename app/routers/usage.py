"""使用时长：页面心跳累计程序使用时长；本机游戏进程时长自动归属机主。"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from datetime import datetime, timedelta

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from ..config import DATABASE_URL
from ..database import SessionLocal, get_db
from ..games import GAMES
from ..models import UsageStat, User
from .deps import get_current_user, require_api_key

router = APIRouter(prefix="/api/usage", tags=["usage"])


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _add(db: Session, user_id: int, game: str, seconds: int) -> None:
    seconds = max(5, min(int(seconds), 300))
    day = today_str()
    row = db.query(UsageStat).filter_by(user_id=user_id, game=game, day=day).first()
    if row is None:
        db.add(UsageStat(user_id=user_id, game=game, day=day, seconds=seconds))
    else:
        row.seconds += seconds
    db.commit()


def _series(db: Session, user_id: int, game: str, days: int = 7) -> list[dict]:
    start = datetime.now() - timedelta(days=days - 1)
    out = []
    for i in range(days):
        day = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        row = db.query(UsageStat).filter_by(user_id=user_id, game=game, day=day).first()
        out.append({"day": day, "seconds": row.seconds if row else 0})
    return out


@router.post("/heartbeat", dependencies=[Depends(require_api_key)])
def heartbeat(
    payload: dict = Body(default={}),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    seconds = int((payload or {}).get("seconds") or 60)
    _add(db, user.id, "app", seconds)
    row = db.query(UsageStat).filter_by(user_id=user.id, game="app", day=today_str()).first()
    return {"recorded": True, "today_seconds": row.seconds if row else 0}


@router.get("", dependencies=[Depends(require_api_key)])
def usage_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    owner = db.query(User).filter(User.is_owner.is_(True)).first()
    games: dict = {}
    if owner is not None and owner.id == user.id:
        for key in GAMES:
            series = _series(db, owner.id, key)
            games[key] = {
                "today": next((s["seconds"] for s in series if s["day"] == today_str()), 0),
                "week": series,
            }
    week = _series(db, user.id, "app")
    return {
        "today_app": next((s["seconds"] for s in week if s["day"] == today_str()), 0),
        "week": week,
        "games": games,
    }


def _proc_running(name: str) -> bool:
    if os.name != "nt" or not name:
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {name}"],
            capture_output=True,
            timeout=10,
        )
        return name.lower() in result.stdout.decode("utf-8", "ignore").lower()
    except (OSError, subprocess.TimeoutExpired):
        return False


def _monitor_tick() -> None:
    db = SessionLocal()
    try:
        owner = db.query(User).filter(User.is_owner.is_(True)).first()
        if owner is None:
            return
        for key, spec in GAMES.items():
            if _proc_running(spec.proc_name):
                _add(db, owner.id, key, 60)
    finally:
        db.close()


def start_usage_monitor() -> None:
    """每 60 秒统计一次机主正在运行的游戏时长（仅 Windows 真机，测试环境跳过）。"""
    if os.name != "nt" or "test.db" in DATABASE_URL:
        return

    def loop() -> None:
        while True:
            try:
                _monitor_tick()
            except Exception:  # 监控失败不影响主服务
                pass
            time.sleep(60)

    threading.Thread(target=loop, daemon=True).start()
