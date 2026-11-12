"""官方接入（UID 自动同步）+ 本地 JSON 导入 + 米游社 Cookie 设置。"""

from app.routers import sync as sync_router

FAKE_RECORD = {
    "uid": "100000001",
    "nickname": "开拓者",
    "level": 70,
    "active_days": 500,
    "achievements": 900,
    "stamina_current": 90,
    "stamina_max": 240,
    "characters": [
        {"name": "黄泉", "rarity": 5, "level": 80, "element": "雷", "eidolon": 2, "extra": {"path": "虚无"}},
        {"name": "三月七", "rarity": 4, "level": 70, "element": "冰", "eidolon": 6, "extra": {"path": "存护"}},
    ],
    "challenges": {
        "challenge": {
            "name": "忘却之庭",
            "season": "浑沌回忆·玄都",
            "progress": {"current": 30, "max": 36, "unit": "星"},
            "nodes": [{"name": "第11层", "value": 3, "max": 3}, {"name": "第12层", "value": 1, "max": 3}],
        },
        "rogue": {
            "name": "模拟宇宙",
            "stats": [{"label": "最高积分", "value": 65535}],
            "records": [{"name": "差分宇宙", "score": 65535, "finished": True}],
        },
    },
}


def test_bind_hsr_syncs_by_uid(client, auth_headers, monkeypatch):
    calls = {}

    def fake_fetch(uid=None, cookie=None, db=None):
        calls["uid"] = uid
        return FAKE_RECORD

    monkeypatch.setattr(sync_router, "fetch_hsr_record", fake_fetch)
    resp = client.post("/api/bind/hsr", json={"uid": "100000001"}, headers=auth_headers)
    assert resp.status_code == 200
    assert calls["uid"] == "100000001"

    me = client.get("/api/me", headers=auth_headers).json()
    hsr = me["games"]["hsr"]
    assert hsr["profile"]["uid"] == "100000001"
    assert hsr["profile"]["level"] == 70
    assert len(hsr["characters"]) == 2
    assert hsr["characters"][0]["eidolon"] == 2
    assert hsr["characters"][0]["extra"]["path"] == "虚无"
    assert hsr["challenges"]["challenge"]["progress"] == {"current": 30, "max": 36, "unit": "星"}
    assert hsr["challenges"]["challenge"]["nodes"][0]["value"] == 3
    assert hsr["challenges"]["rogue"]["stats"][0]["value"] == 65535


def test_bind_requires_uid(client, auth_headers):
    assert client.post("/api/bind/hsr", json={}, headers=auth_headers).status_code == 422


def test_bind_wuwa_not_available(client, auth_headers):
    resp = client.post("/api/bind/wuwa", json={"uid": "600012345"}, headers=auth_headers)
    assert resp.status_code == 501
    assert "没有公开的玩家数据接口" in resp.json()["detail"]


def test_bind_unknown_game(client, auth_headers):
    assert client.post("/api/bind/nope", json={"uid": "1"}, headers=auth_headers).status_code == 404


def test_bind_error_maps_to_400(client, auth_headers, monkeypatch):
    def boom(uid=None, cookie=None, db=None):
        raise sync_router.SyncError("Cookie 已过期")

    monkeypatch.setattr(sync_router, "fetch_hsr_record", boom)
    resp = client.post("/api/bind/hsr", json={"uid": "100000001"}, headers=auth_headers)
    assert resp.status_code == 400
    assert "Cookie 已过期" in resp.json()["detail"]


def test_import_json_with_challenges(client, auth_headers):
    payload = {
        "uid": "600012345",
        "nickname": "漂泊者",
        "level": 60,
        "active_days": 300,
        "achievements": 500,
        "stamina": {"current": 120, "max": 240},
        "resources": {"astrites": 12345},
        "characters": [{"name": "忌炎", "rarity": 5, "level": 80, "element": "雷", "eidolon": 1}],
        "challenges": {
            "tower": {
                "name": "逆境深塔",
                "season": "1.4 版本",
                "progress": {"current": 24, "max": 30, "unit": "星"},
                "nodes": [{"name": "左塔", "value": 10, "max": 12}],
            }
        },
    }
    resp = client.post("/api/import/wuwa", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    wuwa = resp.json()["games"]["wuwa"]
    assert wuwa["profile"]["uid"] == "600012345"
    assert wuwa["characters"][0]["eidolon"] == 1
    assert wuwa["challenges"]["tower"]["progress"]["current"] == 24
    assert wuwa["stamina"]["current"] == 120


def test_import_bad_json(client, auth_headers):
    assert client.post("/api/import/wuwa", json={"level": "不是数字"}, headers=auth_headers).status_code == 422


def test_cookie_settings_roundtrip(client, auth_headers):
    assert client.get("/api/settings/hoyolab-cookie", headers=auth_headers).json()["configured"] is False
    resp = client.put(
        "/api/settings/hoyolab-cookie",
        json={"cookie": "ltoken=abc; ltuid=123; cookie_token=xyz"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["configured"] is True
    got = client.get("/api/settings/hoyolab-cookie", headers=auth_headers).json()
    assert got["value"].startswith("ltoken=abc")
    assert got["tail"] == "oken=xyz"


def test_unbind_clears_profile(client, auth_headers, monkeypatch):
    def fake_fetch(uid=None, cookie=None, db=None):
        return FAKE_RECORD

    monkeypatch.setattr(sync_router, "fetch_hsr_record", fake_fetch)
    assert client.post("/api/bind/hsr", json={"uid": "100000001"}, headers=auth_headers).status_code == 200
    assert "hsr" in client.get("/api/me", headers=auth_headers).json()["games"]

    resp = client.delete("/api/bind/hsr", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["unbound"] is True
    assert "hsr" not in client.get("/api/me", headers=auth_headers).json()["games"]

    assert client.delete("/api/bind/hsr", headers=auth_headers).json()["unbound"] is False
    assert client.delete("/api/bind/nope", headers=auth_headers).status_code == 404


def test_auto_login_by_password_syncs(client, auth_headers, monkeypatch):
    calls = {}

    def fake_login(account, password):
        calls["account"] = account
        return "ltoken=fake; ltuid=123; cookie_token=fake_cookie_token"

    def fake_save(cookie):
        calls["cookie"] = cookie

    def fake_fetch(uid=None, cookie=None, db=None):
        calls["uid"] = uid
        return FAKE_RECORD

    monkeypatch.setattr(sync_router, "login_by_password", fake_login)
    monkeypatch.setattr(sync_router, "save_cookie_to_db", fake_save)
    monkeypatch.setattr(sync_router, "fetch_hsr_record", fake_fetch)

    resp = client.post(
        "/api/hoyolab/auto-login",
        json={"account": "a@b.c", "password": "secret", "uid": "100000001"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "synced"
    assert calls["account"] == "a@b.c"
    assert "ltoken=fake" in calls["cookie"]
    assert calls["uid"] == "100000001"
    assert "hsr" in client.get("/api/me", headers=auth_headers).json()["games"]


def test_auto_login_requires_uid(client, auth_headers):
    resp = client.post("/api/hoyolab/auto-login", json={"account": "a", "password": "b"}, headers=auth_headers)
    assert resp.status_code == 422


def test_auto_login_falls_back_to_browser(client, auth_headers, monkeypatch):
    called = {}

    def fake_login(account, password):
        raise sync_router.NeedCaptcha("captcha")

    def fake_browser(account, password, on_captured=None):
        called["browser"] = True

    monkeypatch.setattr(sync_router, "login_by_password", fake_login)
    monkeypatch.setattr(sync_router, "start_browser_capture", fake_browser)

    resp = client.post(
        "/api/hoyolab/auto-login",
        json={"account": "a", "password": "b", "uid": "100000001"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "auto"
    assert called["browser"] is True


def test_auto_login_bad_credentials_400(client, auth_headers, monkeypatch):
    def boom(account, password):
        raise RuntimeError("账号或密码错误")

    monkeypatch.setattr(sync_router, "login_by_password", boom)
    resp = client.post(
        "/api/hoyolab/auto-login",
        json={"account": "a", "password": "b", "uid": "100000001"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "账号或密码错误" in resp.json()["detail"]
