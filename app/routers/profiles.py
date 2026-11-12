"""手动录入 / 校对后确认的写入接口。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..games import merged_games
from ..database import get_db
from ..models import User
from ..schemas import ProfileUpdate
from ..services.profiles import apply_profile_update
from ..services.serializers import share_payload
from .deps import get_current_user, require_api_key

router = APIRouter(prefix="/api", tags=["profiles"])


@router.post("/profiles/{game}", dependencies=[Depends(require_api_key)])
def upsert_profile(
    game: str,
    payload: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    registry = merged_games(db)
    if game not in registry:
        raise HTTPException(status_code=404, detail=f"未知游戏: {game}，支持: {', '.join(registry)}")
    player = apply_profile_update(db, game, payload, user)
    return share_payload(db, player)
