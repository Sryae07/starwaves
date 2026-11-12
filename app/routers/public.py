"""公开只读接口：分享页 + 管理页自用。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Player
from ..services.serializers import share_payload
from .deps import require_api_key

router = APIRouter(prefix="/api", tags=["public"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "app": "StarWaves", "version": "0.1.0"}


@router.get("/share/{share_id}")
def get_shared_profile(share_id: str, db: Session = Depends(get_db)) -> dict:
    player = db.query(Player).filter(Player.share_id == share_id).first()
    if player is None:
        raise HTTPException(status_code=404, detail="分享链接不存在或已失效")
    return share_payload(db, player)


@router.get("/me", dependencies=[Depends(require_api_key)])
def get_my_profile(db: Session = Depends(get_db)) -> dict:
    player = db.query(Player).order_by(Player.id.asc()).first()
    if player is None:
        player = Player(nickname="旅行者")
        db.add(player)
        db.commit()
        db.refresh(player)
    return share_payload(db, player)
