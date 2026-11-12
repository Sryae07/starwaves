"""公开只读接口：分享页 + 管理页自用。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Player, User
from ..security import mask_phone
from ..services.serializers import share_payload
from ..services.profiles import get_or_create_player
from .deps import get_current_user, require_api_key

router = APIRouter(prefix="/api", tags=["public"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "app": "StarWaves", "version": "0.3.0"}


@router.get("/share/{share_id}")
def get_shared_profile(share_id: str, db: Session = Depends(get_db)) -> dict:
    player = db.query(Player).filter(Player.share_id == share_id).first()
    if player is None:
        raise HTTPException(status_code=404, detail="分享链接不存在或已失效")
    return share_payload(db, player)


@router.get("/me", dependencies=[Depends(require_api_key)])
def get_my_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    player = get_or_create_player(db, user)
    if player.nickname != user.username:
        player.nickname = user.username
        db.commit()
    payload = share_payload(db, player)
    payload["user"] = {
        "id": user.id,
        "username": user.username,
        "phone": mask_phone(user.phone) if user.phone else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
    return payload
