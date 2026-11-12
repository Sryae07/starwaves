"""官方资讯聚合：把各游戏的官方公告 / 动态汇到一个信息流。

架构：
- 数据源以 Provider 插件的形式挂在 app/games.py 注册表的 GameSpec.news 上，
  新增游戏时直接复用已有 Provider（如 miyoushe / kuro_site），
  或在此新增一个 Provider 类并登记；
- 结果带 TTL 缓存（默认 5 分钟），页面轮询不会打到上游高频风控；
- 任何数据源失败都降级为「空列表 + 错误说明」（有旧缓存时返回旧缓存），
  绝不影响其它游戏与看板主流程。

风险提示：米游社论坛接口为社区协议，随时可能调整字段或风控；
库洛官网 JSON 为官网静态资源。解析均做多候选容错。
"""

from __future__ import annotations

import re
import threading
import time
from datetime import datetime, timedelta, timezone

import httpx

from ..games import GAMES, GameSpec

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
TIMEOUT = 8.0
CACHE_TTL = 300.0

CN_TZ = timezone(timedelta(hours=8))

# game -> (缓存写入时间, 资讯列表)
_caches: dict[str, tuple[float, list[dict]]] = {}
_caches_lock = threading.Lock()
_fetch_locks: dict[str, threading.Lock] = {}
_fetch_locks_guard = threading.Lock()


class NewsSourceError(RuntimeError):
    pass


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CN_TZ)
    return dt.astimezone(timezone.utc).isoformat()


def _strip_html(html: str, limit: int = 140) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _get_json(url: str, *, params: dict | None = None, headers: dict | None = None) -> dict | list:
    """独立的网络入口，便于测试注入假响应。"""
    with httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        resp = client.get(url, params=params, headers=headers or {})
        resp.raise_for_status()
        return resp.json()


class MiyousheProvider:
    """米游社官方论坛帖子（公告 + 活动）。"""

    name = "miyoushe"

    def fetch(self, spec: GameSpec) -> list[dict]:
        forum_id = spec.news["forum_id"]
        payload = _get_json(
            "https://bbs-api.miyoushe.com/post/wapi/getForumPostList",
            params={
                "forum_id": forum_id,
                "is_good": "false",
                "is_hot": "false",
                "page_size": 20,
                "sort_type": 1,
            },
            headers={
                "Referer": "https://www.miyoushe.com/",
                "x-rpc-app_version": "2.51.1",
                "x-rpc-client_type": "5",
            },
        )
        if not isinstance(payload, dict) or payload.get("retcode") not in (0, None):
            raise NewsSourceError(f"米游社接口返回异常: {(payload or {}).get('message', payload)}")
        posts = [
            item.get("post") or {}
            for item in ((payload.get("data") or {}).get("list") or [])
            if isinstance(item, dict)
        ]
        official = [p for p in posts if (p.get("post_status") or {}).get("is_official")]
        chosen = official if len(official) >= 3 else posts
        chosen.sort(key=lambda p: p.get("created_at") or 0, reverse=True)
        items = []
        for post in chosen:
            post_id = post.get("post_id")
            if not post_id:
                continue
            created = post.get("created_at")
            published = (
                datetime.fromtimestamp(created, tz=CN_TZ) if isinstance(created, (int, float)) else None
            )
            images = post.get("images") or []
            items.append(
                {
                    "id": f"{spec.key}-{post_id}",
                    "game": spec.key,
                    "title": (post.get("subject") or "").strip() or "无标题",
                    "summary": _strip_html(post.get("content")),
                    "url": f"{spec.news['article_base']}{post_id}",
                    "cover": images[0] if images else "",
                    "published_at": _iso(published),
                    "source": spec.news.get("source_label", "米游社"),
                    "category": "官方" if (post.get("post_status") or {}).get("is_official") else "社区",
                    "official": bool((post.get("post_status") or {}).get("is_official")),
                }
            )
        return items


class KuroNewsProvider:
    """库洛《鸣潮》官网资讯 JSON（公告 / 新闻 / 活动）。"""

    name = "kuro_site"
    TYPE_LABELS = {"52": "公告", "51": "新闻", "53": "活动"}

    def fetch(self, spec: GameSpec) -> list[dict]:
        payload = _get_json(spec.news["json_url"])
        if not isinstance(payload, list):
            raise NewsSourceError("鸣潮官网资讯返回结构异常")
        articles = sorted(
            payload,
            key=lambda a: (int(a.get("top") or 0), a.get("createTime") or ""),
            reverse=True,
        )
        items = []
        for article in articles[:20]:
            article_id = article.get("articleId")
            if article_id is None:
                continue
            created = article.get("createTime") or article.get("startTime")
            published = None
            if created:
                try:
                    published = datetime.strptime(created, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CN_TZ)
                except ValueError:
                    published = None
            items.append(
                {
                    "id": f"{spec.key}-{article_id}",
                    "game": spec.key,
                    "title": (article.get("articleTitle") or "").strip() or "无标题",
                    "summary": _strip_html(article.get("articleContent")),
                    "url": f"{spec.news['article_base']}{article_id}",
                    "cover": article.get("suggestCover") or article.get("articleCover") or "",
                    "published_at": _iso(published),
                    "source": spec.news.get("source_label", "官网"),
                    "category": self.TYPE_LABELS.get(str(article.get("articleType")), "资讯"),
                    "official": True,
                }
            )
        return items


PROVIDERS: dict[str, object] = {
    "miyoushe": MiyousheProvider(),
    "kuro_site": KuroNewsProvider(),
}


def _lock_for(game: str) -> threading.Lock:
    with _fetch_locks_guard:
        return _fetch_locks.setdefault(game, threading.Lock())


def fetch_game_news(game: str, limit: int = 12, registry: dict[str, GameSpec] | None = None) -> dict:
    """拉取单个游戏的资讯：命中缓存直接返回，失败时降级为旧缓存或空列表。"""
    specs = registry or GAMES
    spec = specs.get(game)
    if spec is None:
        return {"items": [], "source": "", "error": f"未注册的游戏: {game}"}
    if not spec.news:
        return {"items": [], "source": "", "error": None}

    now = time.time()
    with _caches_lock:
        cached = _caches.get(game)
        if cached and now - cached[0] < CACHE_TTL:
            return {"items": cached[1][:limit], "source": spec.news.get("source_label", ""), "error": None}

    provider = PROVIDERS.get(spec.news.get("provider", ""))
    if provider is None:
        return {"items": [], "source": spec.news.get("source_label", ""), "error": f"未配置资讯数据源: {spec.key}"}
    with _lock_for(game):
        with _caches_lock:
            cached = _caches.get(game)
            if cached and time.time() - cached[0] < CACHE_TTL:
                return {"items": cached[1][:limit], "source": spec.news.get("source_label", ""), "error": None}
        try:
            items = provider.fetch(spec)
        except Exception as exc:  # noqa: BLE001 上游任何异常都降级
            with _caches_lock:
                cached = _caches.get(game)
            if cached:
                return {
                    "items": cached[1][:limit],
                    "source": spec.news.get("source_label", ""),
                    "error": f"刷新失败，展示 {time.strftime('%H:%M')} 前缓存：{exc}",
                }
            return {"items": [], "source": spec.news.get("source_label", ""), "error": f"获取失败: {exc}"}
        with _caches_lock:
            _caches[game] = (time.time(), items)
        return {"items": items[:limit], "source": spec.news.get("source_label", ""), "error": None}


def clear_news_cache() -> None:
    with _caches_lock:
        _caches.clear()
