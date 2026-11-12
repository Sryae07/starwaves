"""资讯聚合 + 游戏注册表公开接口。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from ..games import GAMES, game_meta
from ..services.news import fetch_game_news

router = APIRouter(prefix="/api", tags=["news"])


@router.get("/games")
def list_games() -> dict:
    """游戏注册表元数据：前端看板 / 资讯页据此动态渲染。"""
    return {"games": game_meta()}


@router.get("/news")
def get_news(
    game: list[str] | None = Query(default=None),
    limit: int = Query(default=12, ge=1, le=30),
) -> dict:
    """合并各游戏的官方资讯，按发布时间倒序。"""
    if game is None:
        keys = list(GAMES)
    else:
        keys = [g for g in game if g in GAMES]
    if not keys:
        return {"updated_at": datetime.now(timezone.utc).isoformat(), "items": [], "sources": {}}
    with ThreadPoolExecutor(max_workers=len(keys)) as pool:
        results = dict(zip(keys, pool.map(lambda k: fetch_game_news(k, limit=limit), keys)))
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
