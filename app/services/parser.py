"""OCR 文本解析：把 PaddleOCR 输出的原始文本行转成结构化字段。

关键词表是数据驱动的，游戏截图排版变化时只需在 GAME_FIELDS 里增减关键词，
不需要改动解析逻辑。
"""

from __future__ import annotations

import re

FULLWIDTH_MAP = {ord(c): d for c, d in zip("０１２３４５６７８９", "0123456789")}
FULLWIDTH_MAP.update({ord("／"): "/", ord("："): ":", ord("．"): "."})

GAME_FIELDS = {
    "hsr": {
        "uid": ["uid"],
        "level": ["开拓等级", "等级"],
        "active_days": ["活跃天数"],
        "achievements": ["成就"],
        "stamina": ["开拓力"],
        "characters": ["角色数量", "拥有角色", "角色数"],
    },
    "wuwa": {
        "uid": ["uid"],
        "level": ["联觉等级", "等级"],
        "active_days": ["活跃天数"],
        "achievements": ["成就"],
        "stamina": ["结晶波片", "波片"],
        "characters": ["角色数量", "共鸣者数量", "角色数"],
    },
}


def normalize(text: str) -> str:
    """全角数字/符号转半角，消除 OCR 对全半角的随机输出。"""
    return text.translate(FULLWIDTH_MAP)


def parse_ocr_text(text: str, game: str) -> dict:
    if game not in GAME_FIELDS:
        raise ValueError(f"未知游戏: {game}，支持: {', '.join(GAME_FIELDS)}")
    fields = GAME_FIELDS[game]
    lines = [normalize(line).strip() for line in text.splitlines() if line.strip()]
    parsed = {
        "uid": None,
        "level": None,
        "active_days": None,
        "achievements": None,
        "stamina_current": None,
        "stamina_max": None,
        "characters": None,
    }

    def first_line_with(keywords: list[str]) -> str | None:
        for kw in keywords:
            for line in lines:
                if kw.lower() in line.lower():
                    return line
        return None

    stamina_line = first_line_with(fields["stamina"])
    if stamina_line:
        pair = re.search(r"(\d+)\s*/\s*(\d+)", stamina_line)
        if pair:
            parsed["stamina_current"] = int(pair.group(1))
            parsed["stamina_max"] = int(pair.group(2))
        else:
            nums = re.findall(r"\d+", stamina_line)
            if nums:
                parsed["stamina_current"] = int(nums[0])

    for key in ("level", "active_days", "achievements", "characters"):
        line = first_line_with(fields[key])
        if line:
            nums = re.findall(r"\d+", line)
            if nums:
                parsed[key] = int(nums[0])

    uid_line = first_line_with(fields["uid"])
    if uid_line:
        runs = re.findall(r"\d+", uid_line)
        if runs:
            parsed["uid"] = max(runs, key=len)

    parsed["missing_fields"] = [k for k, v in parsed.items() if v is None]
    return parsed
