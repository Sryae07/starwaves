"""网页「接入游戏」：自定义游戏的增删（读接口在 routers/news.py 的 /api/games）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..games import BUILTIN_KEYS, game_meta, merged_games
from ..models import CustomGame, Profile
from ..schemas import GameCreate
from .deps import require_api_key, require_owner

router = APIRouter(prefix="/api", tags=["games"])


def _meta(db: Session) -> dict:
    return {"games": game_meta(merged_games(db))}


@router.post("/games", dependencies=[Depends(require_api_key), Depends(require_owner)])
def create_game(payload: GameCreate, db: Session = Depends(get_db)) -> dict:
    if payload.key in BUILTIN_KEYS:
        raise HTTPException(status_code=400, detail=f"{payload.key} 是内置游戏标识，不能覆盖，请换一个 key")
    if db.query(CustomGame).filter(CustomGame.key == payload.key).first():
        raise HTTPException(status_code=409, detail=f"游戏 {payload.key} 已接入，无需重复添加")
    db.add(
        CustomGame(
            key=payload.key,
            label=payload.label,
            tagline=payload.tagline,
            emoji=payload.emoji,
            stamina_name=payload.stamina_name,
            minutes_per_point=payload.minutes_per_point,
            cap=payload.cap,
            color_a=payload.color_a,
            color_b=payload.color_b,
            resource_labels=payload.resource_labels,
        )
    )
    db.commit()
    return {"created": True, **_meta(db)}


@router.delete("/games/{key}", dependencies=[Depends(require_api_key), Depends(require_owner)])
def delete_game(key: str, db: Session = Depends(get_db)) -> dict:
    if key in BUILTIN_KEYS:
        raise HTTPException(status_code=400, detail=f"{key} 是内置游戏，不能移除")
    row = db.query(CustomGame).filter(CustomGame.key == key).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"自定义游戏 {key} 不存在")
    has_profile = db.query(Profile).filter(Profile.game == key).first() is not None
    if has_profile:
        raise HTTPException(
            status_code=409,
            detail=f"「{row.label}」已有游戏数据，暂不能移除（历史快照按 key 归档，删除会丢失归档）",
        )
    db.delete(row)
    db.commit()
    return {"deleted": True, **_meta(db)}
