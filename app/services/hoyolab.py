"""星穹铁道战绩同步（米游社「战绩」社区协议，非官方接口）。

能力：
- 输入 UID（或自动取账号下第一个角色）拉取等级/活跃天数/成就/体力/角色（含命座与命途）；
- 拉取挑战进度：忘却之庭 / 虚构叙事 / 末日幻影 / 模拟宇宙，单接口失败不影响整体同步；
- Cookie 优先读站点设置（数据库，看板内可配置），未设置时回退 .env 的 HKRPG_COOKIE。

风险提示：协议为社区逆向，随时可能失效或被风控，仅供个人学习使用。
Cookie 仅保存在本机数据库 / .env，不写入日志与响应。
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from ..config import HKRPG_COOKIE, HKRPG_SERVER, HKRPG_UID
from ..models import SiteSetting

HOST = "https://api-takumi-record.mihoyo.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

CHALLENGE_SECTIONS = (
    ("challenge", "忘却之庭", "星"),
    ("challenge_story", "虚构叙事", "分"),
    ("challenge_boss", "末日幻影", "分"),
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


def _iso_ts(seconds) -> str:
    if not seconds:
        return ""
    try:
        return datetime.fromtimestamp(int(seconds), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return ""


def get_hoyolab_cookie(db=None) -> str:
    """优先数据库设置（看板内配置），回退 .env。"""
    if db is not None:
        row = db.query(SiteSetting).filter(SiteSetting.key == "hoyolab_cookie").first()
        if row and row.value.strip():
            return row.value.strip()
    return HKRPG_COOKIE


def _normalize_challenge(section: str, data: dict) -> dict:
    """把米游社挑战接口的 groups/nodes 归一化成前端可直接渲染的结构。"""
    nodes = []
    for group in data.get("groups") or []:
        group_name = group.get("name") or ""
        for node in group.get("nodes") or []:
            star = node.get("cur_star")
            score = node.get("score")
            value = star if star is not None else score
            max_value = node.get("max_star") if star is not None else node.get("max_score")
            nodes.append(
                {
                    "name": f"{group_name}·{node.get('name') or ''}".strip("·"),
                    "value": value or 0,
                    "max": max_value or 0,
                }
            )
    if not nodes:
        return {}
    current = sum(n["value"] for n in nodes)
    maximum = sum(n["max"] for n in nodes)
    return {
        "name": section,
        "season": data.get("schedule_name") or data.get("season") or "",
        "progress": {"current": current, "max": maximum, "unit": data.get("_unit", "分")},
        "nodes": nodes,
        "updated_at": _iso_ts(data.get("current_end_time") or data.get("begin_time")),
    }


def fetch_hsr_record(uid: str | None = None, cookie: str | None = None, db=None) -> dict:
    cookie = cookie or get_hoyolab_cookie(db)
    if not cookie:
        raise SyncError(
            "未配置米游社 Cookie。请在看板「接入游戏」弹窗里粘贴米游社 Cookie"
            "（需包含 ltoken / ltuid / cookie_token），或在 .env 设置 HKRPG_COOKIE。"
        )
    headers = {
        "User-Agent": USER_AGENT,
        "Cookie": cookie,
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
        want_uid = (uid or "").strip() or HKRPG_UID
        if want_uid:
            role = next((r for r in roles if str(r.get("role_id")) == str(want_uid)), None)
            if role is None:
                raise SyncError(
                    f"该账号下未找到 UID {want_uid} 的星穹铁道角色，"
                    "请确认 UID 与登录的米游社账号对应（自动同步只能读取自己账号的数据）。"
                )
        if role is None and roles:
            role = roles[0]
        if role is None:
            raise SyncError(
                "未找到星穹铁道角色记录，请检查 HKRPG_SERVER / Cookie 是否匹配。"
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

        challenges: dict = {}
        for path, label, unit in CHALLENGE_SECTIONS:
            try:
                resp = client.get(
                    f"{HOST}/game_record/app/hkrpg/api/{path}",
                    params={"server": HKRPG_SERVER, "role_id": role_id, "schedule_type": 1},
                )
                resp.raise_for_status()
                payload = resp.json()
                _check_retcode(payload)
                section = payload.get("data") or {}
                if not section.get("has_data", True) and not (section.get("groups")):
                    continue
                section["_unit"] = unit
                normalized = _normalize_challenge(label, section)
                if normalized:
                    challenges[path] = normalized
            except (httpx.HTTPError, SyncError, ValueError):
                continue  # 单个挑战接口失败不影响整体同步

        try:
            rogue_resp = client.get(
                f"{HOST}/game_record/app/hkrpg/api/rogue",
                params={"server": HKRPG_SERVER, "role_id": role_id, "schedule_type": 3},
            )
            rogue_resp.raise_for_status()
            rogue_json = rogue_resp.json()
            _check_retcode(rogue_json)
            rogue_data = rogue_json.get("data") or {}
            basic = rogue_data.get("basic_info") or {}
            records = [
                {
                    "name": r.get("name") or "模拟宇宙",
                    "score": r.get("score") or 0,
                    "finished": bool(r.get("finish_time")),
                }
                for r in rogue_data.get("records") or []
            ]
            if basic.get("has_data") or records:
                challenges["rogue"] = {
                    "name": "模拟宇宙",
                    "season": basic.get("season_name") or "",
                    "stats": [
                        {"label": "最高积分", "value": basic.get("points") or 0},
                    ],
                    "records": records,
                    "updated_at": _iso_ts(basic.get("end_time")),
                }
        except (httpx.HTTPError, SyncError, ValueError):
            pass

    avatars = []
    for item in _dig(data, ["avatar_list"], []) or []:
        if not isinstance(item, dict):
            continue
        path_info = item.get("path") or {}
        extra = {}
        if isinstance(path_info, dict) and path_info.get("name"):
            extra["path"] = path_info["name"]
        avatars.append(
            {
                "name": item.get("name") or "",
                "rarity": item.get("rarity") or 4,
                "level": item.get("level") or 1,
                "element": item.get("element") or "",
                "eidolon": item.get("rank") or 0,
                "extra": extra,
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
        "challenges": challenges,
    }
