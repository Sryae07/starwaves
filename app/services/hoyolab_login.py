"""米游社自动接入 Cookie：

通道 1：账号密码直登（passport API）——成功则合成 ltoken/ltuid/cookie_token；
通道 2：需要人机验证时，拉起本机 Edge 打开米游社登录页，用户登录后自动抓取 Cookie 落库。

安全约定：账号密码只在本机进程内本次请求中使用，绝不落盘、不写日志、不进数据库。
"""

from __future__ import annotations

import secrets
import threading
import time

import httpx

from ..config import DATA_DIR
from ..database import SessionLocal
from ..models import SiteSetting

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
LOGIN_URL = "https://user.mihoyo.com/#/login/password"
BBS_HOME = "https://bbs.mihoyo.com/"
BROWSER_PROFILE_DIR = DATA_DIR / "mhy_browser_profile"

BANNER_JS = """
window.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('starwaves-hint')) return;
  const bar = document.createElement('div');
  bar.id = 'starwaves-hint';
  bar.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:2147483647;'
    + 'background:#0b1220;color:#67e8f9;text-align:center;padding:12px 16px;'
    + 'font-size:15px;font-weight:bold;border-bottom:2px solid #22d3ee;'
    + 'font-family:system-ui,sans-serif;';
  bar.textContent = '🌟 StarWaves 自动接入进行中：正在自动登录米游社，请勿关闭本窗口（人机验证会自动尝试通过）';
  document.body && document.body.appendChild(bar);
});
"""


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


def _tokens_to_cookie(login_ticket: str, uid: str) -> str:
    """login_ticket → stoken/ltoken → cookie_token，合成米游社 Cookie 串。"""
    with httpx.Client(timeout=15, headers=_headers()) as client:
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
        cookie_token = _cookie_token_by_stoken(stoken, uid)
        if not cookie_token:
            raise RuntimeError("未能生成 cookie_token，请改用浏览器登录")
        return f"ltoken={ltoken}; ltuid={uid}; cookie_token={cookie_token}"


def login_by_password(account: str, password: str) -> str:
    """密码直登米游社，成功返回 Cookie 字符串；人机/短信验证抛 NeedCaptcha。"""
    with httpx.Client(timeout=15, headers=_headers()) as client:
        resp = client.post(
            "https://passport-api.mihoyo.com/account/ma-cn-passport/web/loginByPassword",
            json={"account": account, "password": password},
        )
        payload = resp.json()
        retcode = payload.get("retcode")
        message = str(payload.get("message") or "")
        if retcode == 1034 or "验证码" in message or "短信" in message:
            raise NeedCaptcha(message or "米哈游要求人机/短信验证，已切换为浏览器自动登录")
        data = _expect_ok(payload, "密码登录")
        info = data.get("data", {})
        login_ticket = info.get("login_ticket")
        uid = str(info.get("account_info", {}).get("uid") or info.get("uid") or "")
        if not login_ticket or not uid:
            raise RuntimeError("登录响应缺少 login_ticket，请改用浏览器登录")
        return _tokens_to_cookie(login_ticket, uid)


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


def _jar_of(context) -> dict:
    try:
        return {c["name"]: c["value"] for c in context.cookies()}
    except Exception:
        return {}


def _make_cookie(jar: dict) -> str:
    return f"ltoken={jar['ltoken']}; ltuid={jar['ltuid']}; cookie_token={jar['cookie_token']}"


def _set_step(step: str, detail: str = "") -> None:
    with _capture_lock:
        _capture_state["step"] = step
        _capture_state["message"] = detail or _capture_state["message"]


def _login_frame(page):
    """定位米游社登录 iframe（账号密码表单、极验、短信验证都在里面）。"""
    for frame in page.frames:
        if "login-platform" in frame.url:
            return frame
    return page.main_frame


def _submit_button(frame):
    """登录页提交按钮：兼容 button / a / [role=button] 与文本中可能存在的空格。"""
    import re

    for selector in ("button", "a", '[role="button"]'):
        loc = frame.locator(selector).filter(has_text=re.compile(r"登\s*录"))
        try:
            if loc.count() > 0:
                return loc.first
        except Exception:
            continue
    return None


def _wait_login_frame(page, timeout_ms: int = 30000):
    """等待登录 iframe 出现并返回（页面跳转后 iframe 可能延迟创建）。"""
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        for frame in page.frames:
            if "login-platform" in frame.url:
                return frame
        page.wait_for_timeout(500)
    return page.main_frame


def _try_solve_geetest(page) -> bool:
    """尝试自动通过极验：智能按钮直接点；滑块则模拟人类轨迹拖拽。
    极验可能出现在登录 iframe 或独立验证 iframe 中，遍历所有 frame。"""
    import random

    for frame in page.frames:
        try:
            smart = frame.locator(
                ".geetest_smart_button, .geetest_btn, .geetest_success_radar_tip"
            )
            if smart.first.is_visible():
                smart.first.click(force=True)
                return True
        except Exception:
            pass
    for frame in page.frames:
        try:
            slider = frame.locator(
                ".geetest_slider_button, .geetest_slide_button, .geetest_radar_btn"
            ).first
            if not slider.is_visible():
                continue
            box = slider.bounding_box()
            if not box:
                continue
            x = box["x"] + box["width"] / 2
            y = box["y"] + box["height"] / 2
            page.mouse.move(x, y)
            page.wait_for_timeout(random.randint(150, 300))
            page.mouse.down()
            distance = 260
            steps = random.randint(24, 42)
            for i in range(1, steps + 1):
                nx = x + distance * i / steps + random.uniform(-2, 2)
                ny = y + random.uniform(-1.5, 1.5)
                page.mouse.move(nx, ny)
                page.wait_for_timeout(random.randint(6, 22))
            page.mouse.up()
            return True
        except Exception:
            continue
    return False


def _detect_login_error(frame) -> str:
    """检测登录表单内是否出现密码错误等提示，出现则返回提示文本。"""
    try:
        text = frame.evaluate(
            "() => { const b = document.body; return b ? b.innerText.slice(0, 600) : ''; }"
        )
    except Exception:
        return ""
    for key in ("账号或密码错误", "密码错误", "验证失败", "登录失败"):
        if key in text:
            return key
    return ""


def _launch_context(p):
    """优先用本机 Edge（真实环境指纹更稳），失败则回退 Playwright 自带 Chromium。"""
    try:
        return p.chromium.launch_persistent_context(
            str(BROWSER_PROFILE_DIR),
            channel="msedge",
            headless=False,
        )
    except Exception:
        return p.chromium.launch_persistent_context(
            str(BROWSER_PROFILE_DIR),
            headless=False,
        )


def auto_login_capture(account: str, password: str, timeout_s: int = 180) -> str:
    """全自动登录：打开登录页 → 自动填账号密码 → 提交 → 自动过极验/短信 → 抓 Cookie。
    通过监听 passport 登录接口响应精确判断状态，全程用 _capture_state 暴露进度。"""
    from playwright.sync_api import sync_playwright

    deadline = time.time() + timeout_s
    BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    login_responses: list = []
    with sync_playwright() as p:
        context = _launch_context(p)
        try:
            context.add_init_script(BANNER_JS)
            page = context.new_page()
            try:
                page.bring_to_front()
            except Exception:
                pass

            def on_response(resp):
                try:
                    if "loginByPassword" in resp.url:
                        login_responses.append(resp.json())
                except Exception:
                    pass

            page.on("response", on_response)
            _set_step("opening", "正在打开米游社登录页…")
            try:
                page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
            except Exception:
                page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            frame = _wait_login_frame(page)
            for _ in range(3):
                try:
                    tab = frame.locator("text=密码登录").first
                    if tab.is_visible():
                        tab.click()
                        page.wait_for_timeout(1500)
                except Exception:
                    pass
                try:
                    if frame.locator('input[name="password"], input[type="password"]').first.is_visible():
                        break
                except Exception:
                    pass
            try:
                frame.wait_for_selector('input[name="password"], input[type="password"]', timeout=20000)
            except Exception:
                pass

            jar = _jar_of(context)
            if jar.get("ltoken") and jar.get("ltuid"):
                _set_step("logged_in", "检测到已登录，正在复用登录态…")
                if jar.get("cookie_token"):
                    return _make_cookie(jar)
                try:
                    page.goto(BBS_HOME, wait_until="domcontentloaded", timeout=15000)
                except Exception:
                    pass
            else:
                _set_step("filling", "正在自动填写账号密码…")
                try:
                    account_loc = frame.locator(
                        'input[name="username"], input[placeholder*="手机"], input[placeholder*="邮箱"]'
                    ).first
                    if account_loc.count() == 0:
                        account_loc = frame.locator(
                            'input[type="tel"], input[type="text"], input[type="email"]'
                        ).first
                    password_loc = frame.locator(
                        'input[name="password"], input[type="password"]'
                    ).first
                    account_loc.fill(account)
                    page.wait_for_timeout(300)
                    password_loc.fill(password)
                    page.wait_for_timeout(300)
                except Exception as exc:
                    raise RuntimeError(
                        "自动填写账号密码失败（登录页结构变化？frame="
                        + frame.url[:120]
                        + "）："
                        + str(exc)
                    ) from exc

                _set_step("submitting", "正在提交登录…")
                try:
                    submit = _submit_button(frame)
                    if submit is not None:
                        submit.click(force=True)
                    else:
                        password_loc.press("Enter")
                except Exception as exc:
                    raise RuntimeError("提交登录失败：" + str(exc)) from exc

            last_token_try = 0.0
            captcha_tries = 0
            sms_sent_at = 0.0
            sms_clicks = 0
            sms_last_submitted = ""
            agree_at = 0.0
            while time.time() < deadline:
                jar = _jar_of(context)
                if jar.get("ltoken") and jar.get("ltuid"):
                    if jar.get("cookie_token"):
                        _set_step("captured", "登录成功，Cookie 已获取")
                        return _make_cookie(jar)
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
                    try:
                        page.goto(BBS_HOME, wait_until="domcontentloaded", timeout=15000)
                    except Exception:
                        pass
                    time.sleep(2)
                    continue

                while login_responses:
                    payload = login_responses.pop()
                    retcode = payload.get("retcode")
                    msg = str(payload.get("message") or "")
                    data = payload.get("data") or {}
                    if retcode == 0 and data.get("login_ticket"):
                        uid = str(
                            data.get("account_info", {}).get("uid")
                            or data.get("uid") or ""
                        )
                        if uid:
                            _set_step("captured", "登录成功，正在换取 Cookie…")
                            return _tokens_to_cookie(data["login_ticket"], uid)
                    if "验证码" in msg or "短信" in msg or "安全验证" in msg:
                        sms_sent_at = 0.0  # 需要短信验证：触发下方发送逻辑
                        continue
                    if retcode == 1034:
                        continue  # 人机验证：交给下方 geetest 逻辑
                    if retcode not in (0, None):
                        raise RuntimeError(
                            msg or f"米游社登录失败（retcode={retcode}）"
                        )

                frame = _wait_login_frame(page, timeout_ms=3000)
                try:
                    agree = frame.locator('button:text-is("同意")').first
                    if agree.is_visible() and time.time() - agree_at > 5:
                        agree_at = time.time()
                        agree.click(force=True)
                        _set_step("submitting", "已自动同意用户协议，正在重新提交登录…")
                        page.wait_for_timeout(1500)
                        submit2 = _submit_button(frame)
                        if submit2 is not None and submit2.is_visible():
                            submit2.click(force=True)
                        continue
                except Exception:
                    pass
                sms_visible = False
                try:
                    sms_input = frame.locator(
                        'input[placeholder*="验证码"], input[placeholder*="短信"]'
                    ).first
                    sms_visible = sms_input.count() > 0 and sms_input.is_visible()
                    if not sms_visible:
                        body_text = frame.evaluate(
                            "() => document.body ? document.body.innerText.slice(0, 800) : ''"
                        ) or ""
                        if "验证码" in body_text:
                            sms_input = frame.locator(
                                'input[inputmode="numeric"], input[type="tel"]'
                            ).first
                            sms_visible = (
                                sms_input.count() > 0 and sms_input.is_visible()
                            )
                except Exception:
                    sms_visible = False
                if sms_visible:
                    if sms_clicks == 0:
                        _set_step("sms", "检测到短信验证：正在自动点击「获取验证码」…")
                    if time.time() - sms_sent_at > 45 and sms_clicks < 3:
                        try:
                            send = frame.locator(
                                'button:has-text("获取验证码"), button:has-text("发送验证码"), button:has-text("获取验证")'
                            ).first
                            if send.is_visible():
                                send.click()
                                sms_clicks += 1
                                sms_sent_at = time.time()
                                _set_step(
                                    "sms",
                                    f"已自动点击「获取验证码」（第 {sms_clicks} 次）。"
                                    "请在弹出的窗口中输入手机收到的 6 位验证码，其余步骤自动完成",
                                )
                        except Exception:
                            pass
                    try:
                        val = (sms_input.input_value() or "").strip()
                        if (
                            len(val) >= 6
                            and val.isdigit()
                            and val != sms_last_submitted
                        ):
                            sms_last_submitted = val
                            _set_step("sms", "已检测到验证码，正在自动提交…")
                            confirm = frame.locator(
                                'button:text-is("确定"), button:text-is("确认"), button:text-is("登录")'
                            ).first
                            if confirm.is_visible():
                                confirm.click()
                            else:
                                sms_input.press("Enter")
                            page.wait_for_timeout(2000)
                    except Exception:
                        pass

                error = _detect_login_error(frame)
                if error and not sms_visible:
                    raise RuntimeError(f"米游社提示：{error}（请检查账号密码后重试）")

                if captcha_tries < 3 and _try_solve_geetest(page):
                    captcha_tries += 1
                    _set_step("captcha", f"检测到人机验证，正在自动通过（第 {captcha_tries} 次）…")
                    page.wait_for_timeout(2500)
                    continue
                if captcha_tries >= 3:
                    _set_step(
                        "captcha",
                        "人机验证自动通过失败，请在弹出的窗口中手动完成一次滑块验证",
                    )

                time.sleep(2)
            raise TimeoutError("自动登录超时（3 分钟），若一直出现人机验证请稍后重试")
        except Exception as exc:
            if "closed" in str(exc).lower() or "target page" in str(exc).lower():
                raise RuntimeError(
                    "检测到登录窗口被关闭，登录中断。请重新点击「自动登录并接入」。"
                ) from exc
            raise
        finally:
            context.close()


def capture_cookie_from_browser(timeout_s: int = 600) -> str:
    """人工兜底通道：打开登录页等用户手动登录（无账号密码时使用）。"""
    from playwright.sync_api import sync_playwright

    deadline = time.time() + timeout_s
    BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(BROWSER_PROFILE_DIR),
            channel="msedge",
            headless=False,
        )
        try:
            context.add_init_script(BANNER_JS)
            page = context.new_page()
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            try:
                page.bring_to_front()
            except Exception:
                pass
            _set_step("waiting", "请在打开的窗口中完成米游社登录，登录成功后自动保存 Cookie")
            last_token_try = 0.0
            while time.time() < deadline:
                jar = _jar_of(context)
                if jar.get("ltoken") and jar.get("ltuid"):
                    if jar.get("cookie_token"):
                        return _make_cookie(jar)
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
                    try:
                        page.goto(BBS_HOME, wait_until="domcontentloaded", timeout=15000)
                    except Exception:
                        pass
                    time.sleep(3)
                    continue
                time.sleep(2)
            raise TimeoutError("等待米游社登录超时（10 分钟）")
        except Exception as exc:
            if "closed" in str(exc).lower() or "target page" in str(exc).lower():
                raise RuntimeError(
                    "检测到登录窗口被关闭，登录中断。请重新点击「自动登录并接入」。"
                ) from exc
            raise
        finally:
            context.close()


_capture_state = {
    "running": False,
    "status": "idle",
    "step": "",
    "message": "",
    "started_at": None,
}
_capture_lock = threading.Lock()


def capture_state() -> dict:
    with _capture_lock:
        return dict(_capture_state)


def set_capture_state(status: str, step: str, message: str = "") -> None:
    """供后台同步线程写入进度（前端轮询 /api/hoyolab/auto-login/status 可见）。"""
    with _capture_lock:
        _capture_state["status"] = status
        _capture_state["step"] = step
        if message:
            _capture_state["message"] = message


def start_browser_capture(
    account: str = "",
    password: str = "",
    on_captured=None,
) -> None:
    """后台线程：全自动（有账号密码）或人工兜底（无账号密码）抓 Cookie 落库。
    同一时间只允许一个抓取任务，重复点击直接复用进行中的任务。
    on_captured 在 Cookie 保存成功后调用（用于自动同步游戏数据）。"""

    def worker() -> None:
        try:
            cookie = (
                auto_login_capture(account, password)
                if account and password
                else capture_cookie_from_browser()
            )
            save_cookie_to_db(cookie)
            with _capture_lock:
                _capture_state.update(
                    running=False,
                    status="captured",
                    step="captured",
                    message="登录成功，Cookie 已自动保存" + ("，正在同步游戏数据…" if on_captured else ""),
                )
            if on_captured is not None:
                on_captured()
        except Exception as exc:  # 用户取消/超时：记录原因，前端可看到
            with _capture_lock:
                _capture_state.update(
                    running=False,
                    status="failed",
                    step="failed",
                    message=str(exc) or "未知错误",
                )

    with _capture_lock:
        if _capture_state["running"]:
            return
        _capture_state.update(
            running=True,
            status="waiting",
            step="opening",
            message="正在启动自动登录…",
            started_at=time.time(),
        )
    threading.Thread(target=worker, daemon=True).start()
