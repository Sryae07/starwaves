"""资讯聚合 + 游戏注册表公开接口。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..games import merged_games
from ..services.news import fetch_game_news

router = APIRouter(prefix="/api", tags=["news"])


@router.get("/games")
def list_games(db: Session = Depends(get_db)) -> dict:
    """游戏注册表元数据（内置 + 网页接入的自定义游戏）：前端据此动态渲染。"""
    from ..games import game_meta

    return {"games": game_meta(merged_games(db))}


@router.get("/news")
def get_news(
    game: list[str] | None = Query(default=None),
    limit: int = Query(default=12, ge=1, le=30),
    db: Session = Depends(get_db),
) -> dict:
    """合并各游戏的官方资讯，按发布时间倒序。"""
    registry = merged_games(db)
    if game is None:
        keys = [k for k in registry if registry[k].news]
    else:
        keys = [g for g in game if g in registry and registry[g].news]
    if not keys:
        return {"updated_at": datetime.now(timezone.utc).isoformat(), "items": [], "sources": {}}
    with ThreadPoolExecutor(max_workers=len(keys)) as pool:
        results = dict(zip(keys, pool.map(lambda k: fetch_game_news(k, limit=limit, registry=registry), keys)))
    items = []
    for key in keys:
        items.extend(results[key]["items"])
    items.sort(key=lambda i: i.get("published_at") or "", reverse=True)
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "items": items[: limit * len(keys)],
        "sources": {
            key: {
                "name": results[key]["source"],
                "error": results[key]["error"],
            }
            for key in keys
        },
    }
