"""数据模型：玩家 -> 游戏档案 -> 快照/角色。"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    nickname: Mapped[str] = mapped_column(String(64), default="旅行者")
    share_id: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, default=lambda: secrets.token_urlsafe(12)
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    profiles: Mapped[list[Profile]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (UniqueConstraint("player_id", "game", name="uq_player_game"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    game: Mapped[str] = mapped_column(String(16), index=True)  # hsr | wuwa
    uid: Mapped[str] = mapped_column(String(32), default="")
    nickname: Mapped[str] = mapped_column(String(64), default="")
    level: Mapped[int] = mapped_column(Integer, default=0)
    active_days: Mapped[int] = mapped_column(Integer, default=0)
    achievements: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    player: Mapped[Player] = relationship(back_populates="profiles")
    snapshots: Mapped[list[Snapshot]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="Snapshot.captured_at.desc()",
    )
    characters: Mapped[list[Character]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), index=True)
    stamina_current: Mapped[int] = mapped_column(Integer, default=0)
    stamina_max: Mapped[int] = mapped_column(Integer, default=0)
    resources: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(16), default="manual")  # manual | ocr | sync
    image_path: Mapped[str] = mapped_column(String(255), default="")
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    profile: Mapped[Profile] = relationship(back_populates="snapshots")


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    rarity: Mapped[int] = mapped_column(Integer, default=4)
    level: Mapped[int] = mapped_column(Integer, default=1)
    element: Mapped[str] = mapped_column(String(32), default="")
    extra: Mapped[dict] = mapped_column(JSON, default=dict)

    profile: Mapped[Profile] = relationship(back_populates="characters")


class CustomGame(Base):
    """用户在网页上「接入」的自定义游戏（看板内新增，无需改代码）。"""

    __tablename__ = "custom_games"

    key: Mapped[str] = mapped_column(String(16), primary_key=True)
    label: Mapped[str] = mapped_column(String(64))
    tagline: Mapped[str] = mapped_column(String(128), default="")
    emoji: Mapped[str] = mapped_column(String(8), default="🎮")
    stamina_name: Mapped[str] = mapped_column(String(32), default="体力")
    minutes_per_point: Mapped[int] = mapped_column(Integer, default=6)
    cap: Mapped[int] = mapped_column(Integer, default=240)
    color_a: Mapped[str] = mapped_column(String(7), default="#a78bfa")
    color_b: Mapped[str] = mapped_column(String(7), default="#67e8f9")
    resource_labels: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
