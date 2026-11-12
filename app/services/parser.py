"""OCR 文本解析：把 PaddleOCR 输出的原始文本行转成结构化字段。

关键词表是数据驱动的，来自 app/games.py 注册表的 ocr_keywords，
游戏截图排版变化或新增游戏时只需改注册表，不需要改动解析逻辑。
"""

from __future__ import annotations

import re

from ..games import GameSpec, get_spec

FULLWIDTH_MAP = {ord(c): d for c, d in zip("０１２３４５６７８９", "0123456789")}
FULLWIDTH_MAP.update({ord("／"): "/", ord("："): ":", ord("．"): "."})


def normalize(text: str) -> str:
    """全角数字/符号转半角，消除 OCR 对全半角的随机输出。"""
    return text.translate(FULLWIDTH_MAP)


def parse_ocr_text(text: str, game: str, registry: dict[str, GameSpec] | None = None) -> dict:
    spec = (registry or {}).get(game)
    if spec is None:
        spec = get_spec(game)
    fields = spec.ocr_keywords
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
