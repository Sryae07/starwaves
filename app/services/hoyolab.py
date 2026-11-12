"""星穹铁道数据同步（米游社社区协议，非官方接口）。

风险提示：
- 该协议为社区逆向，随时可能失效或被风控，仅供个人学习使用；
- Cookie 只从环境变量读取，绝不写入日志、数据库或响应；
- 字段解析做了多候选键容错，若米游社调整字段，可在下方映射处修改。
"""

from __future__ import annotations

import httpx

from ..config import HKRPG_COOKIE, HKRPG_SERVER, HKRPG_UID

HOST = "https://api-takumi-record.mihoyo.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class SyncError(RuntimeError):
    pass


def _dig(data: dict, paths: list[str], default=None):
    for path in paths:
        node = data
        for key in path.split("."):
            if not isinstance(node, dict) or key not in node:
                node = None
                break
            node = node[key]
        if node is not None:
            return node
    return default


def _check_retcode(payload: dict) -> None:
    if payload.get("retcode") not in (0, None):
        raise SyncError(
            f"米游社接口返回错误：retcode={payload.get('retcode')} "
            f"message={payload.get('message')}（Cookie 可能已过期或被风控）"
        )


def fetch_hsr_record() -> dict:
    if not HKRPG_COOKIE:
        raise SyncError(
            "未配置 HKRPG_COOKIE。请在 .env 中填入米游社 Cookie"
            "（需包含 ltoken / ltuid / cookie_token）后重试。"
        )
    headers = {
        "User-Agent": USER_AGENT,
        "Cookie": HKRPG_COOKIE,
        "Referer": "https://webstatic.mihoyo.com/",
        "x-rpc-app_version": "2.51.1",
        "x-rpc-client_type": "5",
    }
    with httpx.Client(timeout=15, headers=headers) as client:
        role_resp = client.get(
            f"{HOST}/game_record/app/hkrpg/api/role/basicInfo",
            params={"server": HKRPG_SERVER, "page": 1, "size": 20},
        )
        role_resp.raise_for_status()
        role_json = role_resp.json()
        _check_retcode(role_json)
        roles = _dig(role_json, ["data.list"], []) or []
        role = None
        if HKRPG_UID:
            role = next((r for r in roles if str(r.get("role_id")) == str(HKRPG_UID)), None)
        if role is None and roles:
            role = roles[0]
        if role is None:
            raise SyncError(
                "未找到星穹铁道角色记录，请检查 HKRPG_SERVER / HKRPG_UID 与 Cookie 是否匹配。"
            )
        role_id = role.get("role_id")
        index_resp = client.get(
            f"{HOST}/game_record/app/hkrpg/api/index",
            params={"server": HKRPG_SERVER, "role_id": role_id},
        )
        index_resp.raise_for_status()
        index_json = index_resp.json()
        _check_retcode(index_json)

    data = index_json.get("data") or {}
    avatars = []
    for item in _dig(data, ["avatar_list"], []) or []:
        if not isinstance(item, dict):
            continue
        avatars.append(
            {
                "name": item.get("name") or "",
                "rarity": item.get("rarity") or 4,
                "level": item.get("level") or 1,
                "element": item.get("element") or "",
            }
        )
    return {
        "uid": str(role_id),
        "nickname": role.get("nickname") or _dig(data, ["role.nickname"], "") or "",
        "level": _dig(data, ["level", "stats.level"], 0) or 0,
        "active_days": _dig(data, ["stats.active_days", "stats.active_day_number"], 0) or 0,
        "achievements": _dig(data, ["stats.achievement_num", "stats.achievement_number"], 0) or 0,
        "stamina_current": _dig(data, ["current_stamina"], 0) or 0,
        "stamina_max": _dig(data, ["max_stamina"], 240) or 240,
        "characters": avatars,
    }
