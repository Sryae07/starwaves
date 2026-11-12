"""API 请求体模型。"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class CharacterIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    rarity: int = Field(default=4, ge=1, le=6)
    level: int = Field(default=1, ge=1, le=120)
    element: str = Field(default="", max_length=32)
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
    source: str = "manual"  # manual | ocr | sync
