"""API 请求体模型。"""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator

COLOR_RE = r"^#[0-9a-fA-F]{6}$"
PHONE_RE = r"^1[3-9]\d{9}$"
USERNAME_RE = r"^[\u4e00-\u9fa5A-Za-z0-9_-]+$"


class SendCodeIn(BaseModel):
    phone: str = Field(pattern=PHONE_RE)


class RegisterIn(BaseModel):
    phone: str = Field(pattern=PHONE_RE)
    code: str = Field(min_length=6, max_length=6)
    username: str = Field(default="", max_length=24)
    password: str = Field(min_length=6, max_length=72)

    @field_validator("username")
    @classmethod
    def _check_username(cls, value: str) -> str:
        value = value.strip()
        if value and (len(value) < 2 or not re.fullmatch(USERNAME_RE, value)):
            raise ValueError("用户名需 2-24 位，仅支持中文/字母/数字/下划线/短横线（留空自动生成）")
        return value


class LoginIn(BaseModel):
    account: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=72)


class CharacterIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    rarity: int = Field(default=4, ge=1, le=6)
    level: int = Field(default=1, ge=1, le=120)
    element: str = Field(default="", max_length=32)
    eidolon: int = Field(default=0, ge=0, le=6)  # 命座 / 共鸣链
    extra: dict = Field(default_factory=dict)


class ProfileUpdate(BaseModel):
    uid: str = ""
    nickname: str = ""
    level: int = Field(default=0, ge=0)
    active_days: int = Field(default=0, ge=0)
    achievements: int = Field(default=0, ge=0)
    stamina_current: int = Field(default=0, ge=0)
    stamina_max: Optional[int] = Field(default=None, ge=1)
    resources: dict = Field(default_factory=dict)
    characters: list[CharacterIn] = Field(default_factory=list)
    challenges: dict = Field(default_factory=dict)  # 挑战进度（深渊/虚构叙事/末日幻影/模拟宇宙…）
    source: str = "manual"  # manual | ocr | sync


class GameCreate(BaseModel):
    """看板「接入游戏」表单：注册一个自定义游戏。"""

    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,15}$")
    label: str = Field(min_length=1, max_length=32)
    tagline: str = Field(default="", max_length=64)
    emoji: str = Field(default="🎮", max_length=8)
    stamina_name: str = Field(default="体力", min_length=1, max_length=16)
    minutes_per_point: int = Field(default=6, ge=1, le=120)
    cap: int = Field(default=240, ge=1, le=100000)
    color_a: str = "#a78bfa"
    color_b: str = "#67e8f9"
    resource_labels: dict[str, str] = Field(default_factory=dict)

    @field_validator("color_a", "color_b")
    @classmethod
    def _check_color(cls, value: str) -> str:
        if not re.fullmatch(COLOR_RE, value):
            raise ValueError("颜色必须是 #RRGGBB 格式")
        return value
