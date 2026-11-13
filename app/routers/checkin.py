"""签到：每天一次，统计使用软件的天数与时长。"""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Checkin, UsageStat, User
from .deps import get_current_user, require_api_key
from .usage import _series, today_str

router = APIRouter(prefix="/api/checkin", tags=["checkin"])


def _stats(db: Session, user: User) -> dict:
    today = today_str()
    days = {row.day for row in db.query(Checkin).filter(Checkin.user_id == user.id).all()}
    checked = today in days

    streak = 0
    cursor = datetime.now() if checked else datetime.now() - timedelta(days=1)
    while cursor.strftime("%Y-%m-%d") in days:
        streak += 1
        cursor -= timedelta(days=1)

    total_seconds = (
        db.query(UsageStat)
        .filter(UsageStat.user_id == user.id, UsageStat.game == "app")
        .with_entities(func.sum(UsageStat.seconds))
        .scalar()
        or 0
    )
    week = _series(db, user.id, "app")
    today_seconds = next((s["seconds"] for s in week if s["day"] == today), 0)
    return {
        "checked_today": checked,
        "streak": streak,
        "total_days": len(days),
        "total_seconds": int(total_seconds),
        "today_seconds": today_seconds,
        "week": week,
    }


@router.post("", dependencies=[Depends(require_api_key)])
def do_checkin(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    today = today_str()
    if db.query(Checkin).filter(Checkin.user_id == user.id, Checkin.day == today).first() is None:
        db.add(Checkin(user_id=user.id, day=today))
        db.commit()
    stats = _stats(db, user)
    return {**stats, "message": "签到成功，明天再来！" if stats["checked_today"] else ""}


@router.get("", dependencies=[Depends(require_api_key)])
def checkin_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return _stats(db, user)
