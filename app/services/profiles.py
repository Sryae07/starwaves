"""写入侧业务逻辑：OCR / 手动 / 同步三种来源统一落库。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..games import get_spec
from ..models import Character, Player, Profile, Snapshot
from ..schemas import ProfileUpdate


def apply_profile_update(db: Session, game: str, payload: ProfileUpdate) -> Player:
    spec = get_spec(game)
    player = db.query(Player).order_by(Player.id.asc()).first()
    if player is None:
        player = Player(nickname="旅行者")
        db.add(player)
        db.flush()

    profile = (
        db.query(Profile)
        .filter(Profile.player_id == player.id, Profile.game == game)
        .first()
    )
    if profile is None:
        profile = Profile(player_id=player.id, game=game)
        db.add(profile)

    profile.uid = payload.uid or profile.uid
    profile.nickname = payload.nickname or profile.nickname
    profile.level = payload.level
    profile.active_days = payload.active_days
    profile.achievements = payload.achievements

    db.add(
        Snapshot(
            profile=profile,
            stamina_current=payload.stamina_current,
            stamina_max=payload.stamina_max or spec.cap,
            resources=payload.resources or {},
            source=payload.source,
        )
    )

    profile.characters.clear()
    for item in payload.characters:
        profile.characters.append(
            Character(
                name=item.name,
                rarity=item.rarity,
                level=item.level,
                element=item.element,
                extra=item.extra or {},
            )
        )

    db.commit()
    db.refresh(player)
    return player
