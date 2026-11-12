"""米游社自动接入 Cookie：

通道 1：账号密码直登（passport API）——成功则合成 ltoken/ltuid/cookie_token；
通道 2：需要人机验证时，拉起本机 Edge 打开米游社登录页，用户登录后自动抓取 Cookie 落库。

安全约定：账号密码只在本机进程内本次请求中使用，绝不落盘、不写日志、不进数据库。
"""

from __future__ import annotations

import secrets
import tempfile
import threading
import time

import httpx

from ..database import SessionLocal
from ..models import SiteSetting

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
BBS_HOME = "https://bbs.mihoyo.com/"
COOKIE_SCOPE_URL = "https://bbs.mihoyo.com/"


class NeedCaptcha(RuntimeError):
    """米哈游要求人机验证，需回退浏览器登录。"""


def _headers() -> dict:
    return {
        "User-Agent": USER_AGENT,
        "Origin": "https://user.mihoyo.com",
        "Referer": "https://user.mihoyo.com/",
        "x-rpc-app_id": "bll8iq97cem8",
        "x-rpc-client_type": "4",
        "x-rpc-device_id": uuid4_hex(),
        "x-rpc-device_fp": uuid4_hex(),
    }


def uuid4_hex() -> str:
    return secrets.token_hex(16)


def _expect_ok(payload: dict, step: str) -> dict:
    if payload.get("retcode") not in (0, None):
        raise RuntimeError(payload.get("message") or f"{step}失败（retcode={payload.get('retcode')}）")
    return payload


def login_by_password(account: str, password: str) -> str:
    """密码直登米游社，成功返回 Cookie 字符串；触发人机验证抛 NeedCaptcha。"""
    with httpx.Client(timeout=15, headers=_headers()) as client:
        resp = client.post(
            "https://passport-api.mihoyo.com/account/ma-cn-passport/web/loginByPassword",
            json={"account": account, "password": password},
        )
        payload = resp.json()
        if payload.get("retcode") == 1034:
            raise NeedCaptcha("米哈游要求人机验证，已切换为浏览器登录")
        data = _expect_ok(payload, "密码登录")
        info = data.get("data", {})
        login_ticket = info.get("login_ticket")
        uid = str(info.get("account_info", {}).get("uid") or info.get("uid") or "")
        if not login_ticket or not uid:
            raise RuntimeError("登录响应缺少 login_ticket，请改用浏览器登录")

        tokens = _expect_ok(
            client.get(
                "https://api-takumi.mihoyo.com/auth/api/getMultiTokenByLoginTicket",
                params={"login_ticket": login_ticket, "token_types": 3, "uid": uid},
            ).json(),
            "换取登录令牌",
        )
        stoken = ltoken = ""
        for item in tokens.get("data", {}).get("list", []):
            name = item.get("name")
            if name == "stoken":
                stoken = item.get("token") or ""
            elif name == "ltoken":
                ltoken = item.get("token") or ""
        if not ltoken or not stoken:
            raise RuntimeError("未能获取登录令牌，请改用浏览器登录")

        account_info = _expect_ok(
            client.get(
                "https://api-takumi.mihoyo.com/auth/api/getCookieAccountInfoBySToken",
                params={"stoken": stoken, "uid": uid},
            ).json(),
            "生成 Cookie",
        )
        cookie_token = (account_info.get("data") or {}).get("cookie_token") or ""
        if not cookie_token:
            raise RuntimeError("未能生成 cookie_token，请改用浏览器登录")
        return f"ltoken={ltoken}; ltuid={uid}; cookie_token={cookie_token}"


def save_cookie_to_db(cookie: str) -> None:
    db = SessionLocal()
    try:
        row = db.query(SiteSetting).filter(SiteSetting.key == "hoyolab_cookie").first()
        if row is None:
            db.add(SiteSetting(key="hoyolab_cookie", value=cookie))
        else:
            row.value = cookie
        db.commit()
    finally:
        db.close()


def _cookie_token_by_stoken(stoken: str, uid: str) -> str:
    """有 stoken 时直接向米游社接口换 cookie_token（兜底，避免等页面种 cookie）。"""
    with httpx.Client(timeout=15, headers=_headers()) as client:
        payload = client.get(
            "https://api-takumi.mihoyo.com/auth/api/getCookieAccountInfoBySToken",
            params={"stoken": stoken, "uid": uid},
        ).json()
        return (payload.get("data") or {}).get("cookie_token") or ""


def capture_cookie_from_browser(timeout_s: int = 600) -> str:
    """拉起本机 Edge 打开米游社社区，等用户登录后抓取 Cookie。

    登录成功后自动补全 cookie_token（优先页面种下，其次用 stoken 换），
    因此抓取成功与否不再依赖登录页是否回跳社区。"""
    from playwright.sync_api import sync_playwright

    deadline = time.time() + timeout_s
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            tempfile.mkdtemp(prefix="starwaves_mhy_"),
            channel="msedge",
            headless=False,
        )
        try:
            page = context.new_page()
            page.goto(BBS_HOME, wait_until="domcontentloaded")
            last_token_try = 0.0
            while time.time() < deadline:
                jar = {c["name"]: c["value"] for c in context.cookies(COOKIE_SCOPE_URL)}
                if jar.get("ltoken") and jar.get("ltuid"):
                    if jar.get("cookie_token"):
                        return (
                            f"ltoken={jar['ltoken']}; ltuid={jar['ltuid']}; "
                            f"cookie_token={jar['cookie_token']}"
                        )
                    if jar.get("stoken") and time.time() - last_token_try > 15:
                        last_token_try = time.time()
                        try:
                            token = _cookie_token_by_stoken(jar["stoken"], jar["ltuid"])
                            if token:
                                return (
                                    f"ltoken={jar['ltoken']}; ltuid={jar['ltuid']}; "
                                    f"cookie_token={token}"
                                )
                        except Exception:
                            pass
                    # 登录完成但 cookie_token 还没种下：回社区首页触发种 cookie
                    try:
                        page.goto(BBS_HOME, wait_until="domcontentloaded", timeout=15000)
                    except Exception:
                        pass
                    time.sleep(3)
                    continue
                time.sleep(2)
            raise TimeoutError("等待米游社登录超时（10 分钟）")
        finally:
            context.close()


_capture_state = {
    "running": False,
    "status": "idle",
    "message": "",
    "started_at": None,
}
_capture_lock = threading.Lock()


def capture_state() -> dict:
    with _capture_lock:
        return dict(_capture_state)


def start_browser_capture() -> None:
    """后台线程：拉起 Edge → 用户登录 → 自动抓 Cookie 落库。
    同一时间只允许一个抓取任务，重复点击直接复用进行中的任务。"""

    def worker() -> None:
        try:
            cookie = capture_cookie_from_browser()
            save_cookie_to_db(cookie)
            with _capture_lock:
                _capture_state.update(
                    running=False, status="captured", message="Cookie 已自动保存"
                )
        except Exception as exc:  # 用户取消/超时：记录原因，前端可看到
            with _capture_lock:
                _capture_state.update(
                    running=False,
                    status="failed",
                    message=str(exc) or "未知错误",
                )

    with _capture_lock:
        if _capture_state["running"]:
            return
        _capture_state.update(
            running=True,
            status="waiting",
            message="已打开 Edge，请在浏览器中完成米游社登录",
            started_at=time.time(),
        )
    threading.Thread(target=worker, daemon=True).start()
