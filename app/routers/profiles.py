"""手动录入 / 校对后确认的写入接口。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..games import GAMES, known_game
from ..database import get_db
from ..schemas import ProfileUpdate
from ..services.profiles import apply_profile_update
from ..services.serializers import share_payload
from .deps import require_api_key

router = APIRouter(prefix="/api", tags=["profiles"])


@router.post("/profiles/{game}", dependencies=[Depends(require_api_key)])
def upsert_profile(game: str, payload: ProfileUpdate, db: Session = Depends(get_db)) -> dict:
    if not known_game(game):
        raise HTTPException(status_code=404, detail=f"未知游戏: {game}，支持: {', '.join(GAMES)}")
    player = apply_profile_update(db, game, payload)
    return share_payload(db, player)
