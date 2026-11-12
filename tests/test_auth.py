"""账号体系：手机验证码注册 / 密码登录 / 会话 / 鉴权隔离。"""

import re


def _send_code(client, phone="13900139000"):
    resp = client.post("/api/auth/send-code", json={"phone": phone})
    assert resp.status_code == 200
    return resp.json()["dev_code"]


def test_register_with_username_and_default_username(client):
    code = _send_code(client)
    resp = client.post(
        "/api/auth/register",
        json={"phone": "13900139000", "code": code, "username": "开拓者一号", "password": "pass123456"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token"]
    assert body["user"]["username"] == "开拓者一号"
    assert body["user"]["phone"] == "139****9000"
    assert body["share_id"]

    # 第二个账号不填用户名 -> 用户 + 随机不重复编号
    code2 = _send_code(client, "13700137000")
    resp2 = client.post(
        "/api/auth/register",
        json={"phone": "13700137000", "code": code2, "username": "", "password": "pass123456"},
    )
    assert resp2.status_code == 200
    name2 = resp2.json()["user"]["username"]
    assert re.fullmatch(r"用户\d+", name2), name2
    assert name2 != "开拓者一号"


def test_duplicate_phone_and_username(client):
    code = _send_code(client)
    payload = {"phone": "13900139000", "code": code, "username": "星海", "password": "pass123456"}
    assert client.post("/api/auth/register", json=payload).status_code == 200

    assert client.post("/api/auth/register", json=payload).status_code == 409
    code3 = _send_code(client, "13600136000")
    resp = client.post(
        "/api/auth/register",
        json={"phone": "13600136000", "code": code3, "username": "星海", "password": "pass123456"},
    )
    assert resp.status_code == 409


def test_wrong_code_and_expired_code(client):
    _send_code(client)
    resp = client.post(
        "/api/auth/register",
        json={"phone": "13900139000", "code": "000000", "username": "任意", "password": "pass123456"},
    )
    assert resp.status_code == 400
    assert "验证码错误" in resp.json()["detail"]

    resp = client.post(
        "/api/auth/register",
        json={"phone": "13500135000", "code": "123456", "username": "无码", "password": "pass123456"},
    )
    assert resp.status_code == 400


def test_send_code_cooldown(client):
    assert client.post("/api/auth/send-code", json={"phone": "13900139000"}).status_code == 200
    assert client.post("/api/auth/send-code", json={"phone": "13900139000"}).status_code == 429


def test_login_by_username_or_phone_and_wrong_password(client):
    code = _send_code(client)
    client.post(
        "/api/auth/register",
        json={"phone": "13900139000", "code": code, "username": "观星者", "password": "pass123456"},
    )
    for account in ("观星者", "13900139000"):
        resp = client.post("/api/auth/login", json={"account": account, "password": "pass123456"})
        assert resp.status_code == 200
        assert resp.json()["user"]["username"] == "观星者"
    assert client.post(
        "/api/auth/login", json={"account": "观星者", "password": "wrong-pass"}
    ).status_code == 401
    assert client.post(
        "/api/auth/login", json={"account": "不存在的人", "password": "pass123456"}
    ).status_code == 401


def test_me_requires_login_and_share_stays_public(client, auth_headers):
    assert client.get("/api/me").status_code == 401
    assert client.post("/api/profiles/hsr", json={"level": 40}).status_code == 401

    client.post("/api/profiles/hsr", json={"level": 40, "stamina_current": 60}, headers=auth_headers)
    me = client.get("/api/me", headers=auth_headers).json()
    share_id = me["player"]["share_id"]
    assert me["player"]["nickname"] == "测试玩家"
    assert client.get(f"/api/share/{share_id}").status_code == 200


def test_accounts_are_isolated(client, auth_headers):
    # 账号 A（auth_headers）录数据
    client.post("/api/profiles/hsr", json={"level": 70, "stamina_current": 90}, headers=auth_headers)
    # 账号 B 注册登录
    code = _send_code(client, "13800138001")
    reg = client.post(
        "/api/auth/register",
        json={"phone": "13800138001", "code": code, "username": "第二个人", "password": "pass123456"},
    ).json()
    headers_b = {"Authorization": f"Bearer {reg['token']}"}
    me_b = client.get("/api/me", headers=headers_b).json()
    assert me_b["player"]["nickname"] == "第二个人"
    assert "hsr" not in me_b["games"]


def test_logout_invalidates_token(client, auth_headers):
    resp = client.post("/api/auth/logout", headers=auth_headers)
    assert resp.status_code == 200
    assert client.get("/api/me", headers=auth_headers).status_code == 401
