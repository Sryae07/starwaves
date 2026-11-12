"""资讯聚合 + 游戏注册表的测试。"""

from datetime import datetime

import pytest

from app.games import get_spec
from app.services import news as news_service


def test_games_endpoint(client):
    resp = client.get("/api/games")
    assert resp.status_code == 200
    games = {g["key"]: g for g in resp.json()["games"]}
    assert {"hsr", "wuwa", "zzz"} <= set(games)
    spec = games["hsr"]
    for field in ("label", "emoji", "stamina_name", "minutes_per_point", "cap", "colors", "syncable"):
        assert field in spec
    assert spec["stamina_name"] == "开拓力"
    assert spec["syncable"] is True
    assert games["wuwa"]["stamina_name"] == "结晶波片"
    assert games["zzz"]["stamina_name"] == "电量"


def test_news_page_route(client):
    resp = client.get("/news")
    assert resp.status_code == 200
    assert "资讯" in resp.text


def test_news_endpoint_with_providers(client, monkeypatch):
    monkeypatch.setattr(news_service, "_caches", {})

    def fake_miyoushe(spec):
        return [
            {
                "id": f"{spec.key}-1",
                "game": spec.key,
                "title": "版本更新公告",
                "summary": "全新版本即将上线",
                "url": "https://example.com/1",
                "cover": "",
                "published_at": "2026-11-12T08:00:00+00:00",
                "source": "米游社",
                "category": "官方",
                "official": True,
            }
        ]

    def fake_kuro(spec):
        return [
            {
                "id": f"{spec.key}-2",
                "game": spec.key,
                "title": "3.8 版本维护预告",
                "summary": "维护时间说明",
                "url": "https://example.com/2",
                "cover": "",
                "published_at": "2026-11-11T02:00:00+00:00",
                "source": "鸣潮官网",
                "category": "公告",
                "official": True,
            }
        ]

    monkeypatch.setattr(news_service.PROVIDERS["miyoushe"], "fetch", fake_miyoushe)
    monkeypatch.setattr(news_service.PROVIDERS["kuro_site"], "fetch", fake_kuro)

    resp = client.get("/api/news", params=[("game", "hsr"), ("game", "wuwa")])
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["items"][0]["game"] == "hsr"  # 按时间倒序，hsr 最新在前
    assert body["sources"]["hsr"]["name"] == "米游社"
    assert body["sources"]["hsr"]["error"] is None
    assert body["sources"]["wuwa"]["name"] == "鸣潮官网"

    # 第二次请求命中缓存，不经过 provider
    resp2 = client.get("/api/news", params=[("game", "hsr")])
    assert resp2.status_code == 200
    assert len(resp2.json()["items"]) == 1


def test_news_unknown_game_filtered(client, monkeypatch):
    monkeypatch.setattr(news_service, "_caches", {})
    monkeypatch.setattr(news_service.PROVIDERS["miyoushe"], "fetch", lambda spec: [])
    resp = client.get("/api/news", params=[("game", "not-a-game")])
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["sources"] == {}


def test_news_provider_failure_degrades(client, monkeypatch):
    monkeypatch.setattr(news_service, "_caches", {})

    def boom(spec):
        raise news_service.NewsSourceError("上游风控")

    monkeypatch.setattr(news_service.PROVIDERS["miyoushe"], "fetch", boom)
    resp = client.get("/api/news", params=[("game", "hsr")])
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert "风控" in body["sources"]["hsr"]["error"]


def test_miyoushe_provider_parse(monkeypatch):
    payload = {
        "retcode": 0,
        "data": {
            "list": [
                {
                    "post": {
                        "post_id": "100",
                        "subject": "玩家帖",
                        "content": "普通内容",
                        "created_at": 1760000000,
                        "images": [],
                        "post_status": {"is_official": False},
                    }
                },
                {
                    "post": {
                        "post_id": "200",
                        "subject": "官方公告",
                        "content": "版本更新",
                        "created_at": 1760001000,
                        "images": ["https://img.example/a.png"],
                        "post_status": {"is_official": True},
                    }
                },
            ]
        },
    }
    monkeypatch.setattr(news_service, "_get_json", lambda *a, **k: payload)
    items = news_service.MiyousheProvider().fetch(get_spec("hsr"))
    # 官方帖优先：至少包含官方公告且按时间倒序
    assert items[0]["title"] == "官方公告"
    assert items[0]["official"] is True
    assert items[0]["url"].endswith("/200")
    assert items[0]["cover"] == "https://img.example/a.png"


def test_kuro_provider_parse(monkeypatch):
    payload = [
        {
            "articleId": 1,
            "articleTitle": "维护公告",
            "articleContent": "<div>服务器将于<p>10 点</p>维护</div>",
            "articleType": 52,
            "createTime": "2026-11-11 10:00:00",
            "top": 0,
        },
        {
            "articleId": 2,
            "articleTitle": "新版本说明",
            "articleContent": "新玩法上线",
            "articleType": 51,
            "createTime": "2026-11-12 09:00:00",
            "top": 1,
        },
    ]
    monkeypatch.setattr(news_service, "_get_json", lambda *a, **k: payload)
    items = news_service.KuroNewsProvider().fetch(get_spec("wuwa"))
    assert items[0]["title"] == "新版本说明"  # top=1 优先
    assert items[0]["category"] == "新闻"
    assert items[1]["category"] == "公告"
    assert items[1]["summary"] == "服务器将于 10 点 维护"
    assert items[1]["url"].endswith("/1")
    assert items[1]["published_at"] == "2026-11-11T02:00:00+00:00"


def test_registry_unknown_game():
    with pytest.raises(ValueError):
        get_spec("genshin")
