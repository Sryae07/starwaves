import os
import tempfile

TEST_DB = os.path.join(tempfile.gettempdir(), "starwaves_test.db")
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["GALLERY_DIR"] = os.path.join(tempfile.gettempdir(), "starwaves_test_gallery")

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_headers(client):
    """注册一个测试账号并返回 Bearer 头（每个测试独立空库，手机号可复用）。"""
    resp = client.post("/api/auth/send-code", json={"phone": "13800138000"})
    assert resp.status_code == 200
    code = resp.json()["dev_code"]
    resp = client.post(
        "/api/auth/register",
        json={"phone": "13800138000", "code": code, "username": "测试玩家", "password": "pass123456"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}
