"""自动同步与接入：
- /api/sync/hsr   星穹铁道米游社战绩同步（可选 uid，走 Cookie 授权）
- /api/bind/{game} 官方式接入：输入 UID 即自动同步（仅星铁，鸣潮无官方接口）
- /api/import/{game} 本地导出 JSON 一键导入（鸣潮等无接口游戏的主力通道）
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..games import merged_games
from ..models import User
from ..schemas import CharacterIn, ProfileUpdate
from ..services.hoyolab import SyncError, fetch_hsr_record
from ..services.profiles import apply_profile_update
from ..services.serializers import share_payload
from .deps import get_current_user, require_api_key

router = APIRouter(prefix="/api", tags=["sync"])


def _sync_hsr(user: User, db: Session, uid: str | None = None) -> dict:
    try:
        record = fetch_hsr_record(uid=uid, db=db)
    except SyncError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    player = apply_profile_update(
        db,
        "hsr",
        ProfileUpdate(
            uid=record["uid"],
            nickname=record["nickname"],
            level=record["level"],
            active_days=record["active_days"],
            achievements=record["achievements"],
            stamina_current=record["stamina_current"],
            stamina_max=record["stamina_max"],
            characters=[CharacterIn(**c) for c in record["characters"]],
            challenges=record.get("challenges") or {},
            source="sync",
        ),
        user,
    )
    return share_payload(db, player)


@router.post("/sync/hsr", dependencies=[Depends(require_api_key)])
def sync_hsr(
    payload: dict = Body(default={}),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return _sync_hsr(user, db, uid=(payload or {}).get("uid"))


@router.post("/bind/{game}", dependencies=[Depends(require_api_key)])
def bind_game(
    game: str,
    payload: dict = Body(default={}),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """官方式接入：输入 UID 自动同步。目前仅星穹铁道支持（需米游社 Cookie）。"""
    registry = merged_games(db)
    spec = registry.get(game)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"未知游戏: {game}，支持: {', '.join(registry)}")
    uid = str((payload or {}).get("uid") or "").strip()
    if not uid:
        raise HTTPException(status_code=422, detail="请填写游戏 UID")
    if game == "hsr":
        return _sync_hsr(user, db, uid=uid)
    raise HTTPException(
        status_code=501,
        detail=(
            f"{spec.label}没有公开的玩家数据接口，无法像官方那样输入 UID 自动同步。"
            "可用方式：① 上传本地工具导出的 JSON（/api/import）；② 截图 OCR；③ 手动录入。"
        ),
    )


@router.delete("/bind/{game}", dependencies=[Depends(require_api_key)])
def unbind_game(
    game: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """解除绑定：清空该游戏档案（角色 / 快照随档案级联删除），可重新接入。"""
    registry = merged_games(db)
    if game not in registry:
        raise HTTPException(status_code=404, detail=f"未知游戏: {game}，支持: {', '.join(registry)}")
    player = user.player
    profile = None
    if player is not None:
        profile = next((p for p in player.profiles if p.game == game), None)
    if profile is None:
        return {"game": game, "unbound": False}
    db.delete(profile)
    db.commit()
    return {"game": game, "unbound": True}


@router.post("/import/{game}", dependencies=[Depends(require_api_key)])
def import_json(
    game: str,
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """本地导出 JSON 契约：uid/nickname/level/active_days/achievements/
    stamina{current,max}/resources/characters/challenges。"""
    registry = merged_games(db)
    spec = registry.get(game)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"未知游戏: {game}，支持: {', '.join(registry)}")
    stamina = payload.get("stamina") or {}
    try:
        update = ProfileUpdate(
            uid=str(payload.get("uid") or ""),
            nickname=payload.get("nickname") or "",
            level=int(payload.get("level") or 0),
            active_days=int(payload.get("active_days") or 0),
            achievements=int(payload.get("achievements") or 0),
            stamina_current=int(stamina.get("current") or 0),
            stamina_max=int(stamina.get("max") or spec.cap),
            resources=payload.get("resources") or {},
            characters=[CharacterIn(**c) for c in payload.get("characters") or []],
            challenges=payload.get("challenges") or {},
            source="sync",
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"JSON 格式有误: {exc}") from exc
    player = apply_profile_update(db, game, update, user)
    return share_payload(db, player)
