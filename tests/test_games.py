"""看板「接入游戏」（自定义游戏）的端到端测试。"""

from app.services.parser import parse_ocr_text

GAME_PAYLOAD = {
    "key": "pgr",
    "label": "战双帕弥什",
    "tagline": "于末日中起舞",
    "emoji": "🤖",
    "stamina_name": "血清",
    "minutes_per_point": 6,
    "cap": 160,
    "color_a": "#f472b6",
    "color_b": "#7c3aed",
    "resource_labels": {"black_card": "黑卡"},
}


def test_create_custom_game(client, auth_headers):
    resp = client.post("/api/games", json=GAME_PAYLOAD, headers=auth_headers)
    assert resp.status_code == 200
    games = {g["key"]: g for g in client.get("/api/games").json()["games"]}
    assert "pgr" in games
    spec = games["pgr"]
    assert spec["label"] == "战双帕弥什"
    assert spec["stamina_name"] == "血清"
    assert spec["cap"] == 160
    assert spec["custom"] is True
    assert spec["syncable"] is False
    assert spec["launchable"] is False
    assert spec["news"] is False
    assert spec["colors"] == {"a": "#f472b6", "b": "#7c3aed"}


def test_custom_game_duplicate_and_builtin_conflict(client, auth_headers):
    client.post("/api/games", json=GAME_PAYLOAD, headers=auth_headers)
    assert client.post("/api/games", json=GAME_PAYLOAD, headers=auth_headers).status_code == 409
    assert client.post("/api/games", json={**GAME_PAYLOAD, "key": "hsr"}, headers=auth_headers).status_code == 400
    assert client.post("/api/games", json={**GAME_PAYLOAD, "key": "Bad-Key!"}, headers=auth_headers).status_code == 422
    assert client.post("/api/games", json={**GAME_PAYLOAD, "color_a": "red"}, headers=auth_headers).status_code == 422


def test_custom_game_profile_flow(client, auth_headers):
    client.post("/api/games", json=GAME_PAYLOAD, headers=auth_headers)
    resp = client.post(
        "/api/profiles/pgr",
        json={"level": 88, "active_days": 1200, "stamina_current": 40, "stamina_max": 160},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = client.get("/api/me", headers=auth_headers).json()
    pgr = body["games"]["pgr"]
    assert pgr["label"] == "战双帕弥什"
    assert pgr["stamina"]["name"] == "血清"
    assert pgr["stamina"]["current"] == 40
    assert pgr["stamina"]["minutes_to_full"] == (160 - 40) * 6


def test_custom_game_ocr_parse(client, auth_headers):
    client.post("/api/games", json=GAME_PAYLOAD, headers=auth_headers)
    from app.games import merged_games
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        registry = merged_games(db)
    finally:
        db.close()
    parsed = parse_ocr_text("UID 123456\n等级 88\n活跃天数 999\n成就 100\n血清 40 / 160\n角色数量 60", "pgr", registry)
    assert parsed["level"] == 88
    assert parsed["stamina_current"] == 40
    assert parsed["stamina_max"] == 160
    assert parsed["characters"] == 60


def test_delete_custom_game(client, auth_headers):
    client.post("/api/games", json=GAME_PAYLOAD, headers=auth_headers)
    assert client.delete("/api/games/pgr", headers=auth_headers).status_code == 200
    assert "pgr" not in {g["key"] for g in client.get("/api/games").json()["games"]}
    # 内置游戏不可删
    assert client.delete("/api/games/hsr", headers=auth_headers).status_code == 400


def test_delete_blocked_when_has_data(client, auth_headers):
    client.post("/api/games", json=GAME_PAYLOAD, headers=auth_headers)
    client.post(
        "/api/profiles/pgr",
        json={"level": 10, "stamina_current": 50, "stamina_max": 160},
        headers=auth_headers,
    )
    resp = client.delete("/api/games/pgr", headers=auth_headers)
    assert resp.status_code == 409
    assert "已有游戏数据" in resp.json()["detail"]


def test_news_skips_games_without_source(client, auth_headers):
    client.post("/api/games", json=GAME_PAYLOAD, headers=auth_headers)
    resp = client.get("/api/news")
    assert resp.status_code == 200
    keys = set(resp.json()["sources"].keys())
    assert "pgr" not in keys
