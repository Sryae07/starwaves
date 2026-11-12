"""对外输出序列化：合并双游戏档案 + 体力回满倒计时。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..config import GAME_RULES
from ..models import Player, Profile


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _stamina_payload(profile: Profile) -> dict:
    rule = GAME_RULES[profile.game]
    snapshot = profile.snapshots[0] if profile.snapshots else None
    base = {
        "name": rule["stamina_name"],
        "current": 0,
        "max": rule["cap"],
        "full": False,
        "minutes_to_full": None,
        "full_at": None,
    }
    if snapshot is None:
        return base
    current = snapshot.stamina_current
    cap = snapshot.stamina_max or rule["cap"]
    if current >= cap:
        base.update(current=current, max=cap, full=True, minutes_to_full=0)
        return base
    minutes = (cap - current) * rule["minutes_per_point"]
    full_at = snapshot.captured_at
    if full_at.tzinfo is None:
        full_at = full_at.replace(tzinfo=timezone.utc)
    full_at = full_at + timedelta(minutes=minutes)
    base.update(
        current=current,
        max=cap,
        minutes_to_full=minutes,
        full_at=_iso(full_at),
    )
    return base


def game_payload(profile: Profile) -> dict:
    snapshot = profile.snapshots[0] if profile.snapshots else None
    history = [
        {
            "at": _iso(s.captured_at),
            "current": s.stamina_current,
            "max": s.stamina_max or GAME_RULES[profile.game]["cap"],
            "source": s.source,
        }
        for s in profile.snapshots[:30]
    ]
    history.reverse()  # 最近 30 条，按时间升序便于前端画曲线
    return {
        "label": GAME_RULES[profile.game]["label"],
        "profile": {
            "uid": profile.uid,
            "nickname": profile.nickname,
            "level": profile.level,
            "active_days": profile.active_days,
            "achievements": profile.achievements,
        },
        "stamina": _stamina_payload(profile),
        "resources": snapshot.resources if snapshot else {},
        "characters": [
            {
                "name": c.name,
                "rarity": c.rarity,
                "level": c.level,
                "element": c.element,
                "extra": c.extra or {},
            }
            for c in profile.characters
        ],
        "last_update": (
            {"at": _iso(snapshot.captured_at), "source": snapshot.source} if snapshot else None
        ),
        "history": history,
        "snapshot_count": len(profile.snapshots),
    }


def share_payload(db: Session, player: Player) -> dict:
    games = {p.game: game_payload(p) for p in player.profiles}
    latest = None
    for p in player.profiles:
        if p.updated_at and (latest is None or p.updated_at > latest):
            latest = p.updated_at
    return {
        "player": {"nickname": player.nickname, "share_id": player.share_id},
        "games": games,
        "updated_at": _iso(latest),
    }
