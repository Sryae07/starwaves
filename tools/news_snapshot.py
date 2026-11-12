"""生成 docs/news-data.json 静态资讯快照。

供 GitHub Actions 定时运行：手机访问 GitHub Pages 资讯页时，
即使电脑后端不在线，也能读到最近一次快照的数据。
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.games import GAMES  # noqa: E402
from app.services.news import fetch_game_news  # noqa: E402


def main() -> None:
    games = []
    items = []
    sources = {}
    for key, spec in GAMES.items():
        if not spec.news:
            continue
        games.append({"key": spec.key, "label": spec.label, "emoji": spec.emoji})
        result = fetch_game_news(key, limit=40)
        items.extend(result.get("items") or [])
        sources[key] = {
            "name": result.get("source") or "",
            "error": result.get("error"),
        }
    items.sort(key=lambda it: it.get("published_at") or "", reverse=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "games": games,
        "items": items,
        "sources": sources,
    }
    out = ROOT / "docs" / "news-data.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {out} with {len(items)} items from {len(games)} games")


if __name__ == "__main__":
    main()
