from app.routers import deps

HSR_PAYLOAD = {
    "uid": "100000001",
    "nickname": "列车长",
    "level": 70,
    "active_days": 500,
    "achievements": 900,
    "stamina_current": 100,
    "stamina_max": 240,
    "resources": {"jades": 12345, "credits": 67890},
    "characters": [
        {"name": "开拓者", "rarity": 5, "level": 80, "element": "虚数"},
        {"name": "三月七", "rarity": 4, "level": 70, "element": "冰"},
    ],
    "source": "manual",
}


def test_manual_update_and_share(client, auth_headers):
    resp = client.post("/api/profiles/hsr", json=HSR_PAYLOAD, headers=auth_headers)
    assert resp.status_code == 200

    me = client.get("/api/me", headers=auth_headers).json()
    assert me["user"]["username"] == "测试玩家"
    share_id = me["player"]["share_id"]
    assert share_id

    share = client.get(f"/api/share/{share_id}")
    assert share.status_code == 200
    body = share.json()
    hsr = body["games"]["hsr"]
    assert hsr["profile"]["level"] == 70
    assert len(hsr["characters"]) == 2
    assert hsr["stamina"]["current"] == 100
    assert hsr["stamina"]["minutes_to_full"] == 840
    assert hsr["stamina"]["full"] is False
    assert hsr["snapshot_count"] == 1
    assert len(hsr["history"]) == 1
    assert hsr["history"][0]["current"] == 100
    assert hsr["history"][0]["source"] == "manual"
    assert "wuwa" not in body["games"]


def test_full_stamina(client, auth_headers):
    client.post(
        "/api/profiles/wuwa",
        json={"level": 60, "active_days": 300, "stamina_current": 240, "stamina_max": 240},
        headers=auth_headers,
    )
    me = client.get("/api/me", headers=auth_headers).json()
    wuwa = me["games"]["wuwa"]
    assert wuwa["stamina"]["full"] is True
    assert wuwa["stamina"]["full_at"] is None


def test_history_accumulates(client, auth_headers):
    client.post("/api/profiles/wuwa", json={"stamina_current": 100, "stamina_max": 240}, headers=auth_headers)
    client.post("/api/profiles/wuwa", json={"stamina_current": 140, "stamina_max": 240}, headers=auth_headers)
    me = client.get("/api/me", headers=auth_headers).json()
    history = me["games"]["wuwa"]["history"]
    assert len(history) == 2
    assert history[0]["current"] == 100
    assert history[1]["current"] == 140
    assert history[0]["at"] <= history[1]["at"]


def test_share_404(client):
    assert client.get("/api/share/not-exist").status_code == 404


def test_bad_game(client, auth_headers):
    assert client.post("/api/profiles/genshin", json={}, headers=auth_headers).status_code == 404


def test_upload_bad_game(client, auth_headers):
    resp = client.post(
        "/api/upload/genshin", files={"file": ("a.png", b"xx", "image/png")}, headers=auth_headers
    )
    assert resp.status_code == 404


def test_api_key_guard(client, auth_headers, monkeypatch):
    monkeypatch.setattr(deps, "API_KEY", "secret-123")
    assert client.get("/api/me", headers=auth_headers).status_code == 401
    assert client.get("/api/me", headers={**auth_headers, "X-API-Key": "wrong"}).status_code == 401
    assert client.get("/api/me", headers={**auth_headers, "X-API-Key": "secret-123"}).status_code == 200


def test_pages(client):
    home = client.get("/")
    assert home.status_code == 200
    assert "关于本项目" in home.text
    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "StarWaves" in dashboard.text


def test_share_page_route(client):
    assert client.get("/share/whatever").status_code == 200


def test_background_upload_and_reset(client, auth_headers):
    files = {"file": ("bg.png", b"fake-image-bytes", "image/png")}
    resp = client.post("/api/background", files=files, headers=auth_headers)
    assert resp.status_code == 200
    assert client.get("/api/background").status_code == 200
    assert client.delete("/api/background", headers=auth_headers).status_code == 200
    assert client.get("/api/background").status_code == 404


def test_launch_without_path(client, auth_headers, monkeypatch):
    from app.routers import launch

    monkeypatch.setattr(launch, "_resolve_path", lambda game, spec=None: None)
    resp = client.post("/api/launch/hsr", headers=auth_headers)
    assert resp.status_code == 400
    assert "未找到" in resp.json()["detail"]
