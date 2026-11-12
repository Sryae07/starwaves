"""米游社自动同步（星穹铁道，可选能力）。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import CharacterIn, ProfileUpdate
from ..services.hoyolab import SyncError, fetch_hsr_record
from ..services.profiles import apply_profile_update
from ..services.serializers import share_payload
from .deps import require_api_key

router = APIRouter(prefix="/api", tags=["sync"])


@router.post("/sync/hsr", dependencies=[Depends(require_api_key)])
def sync_hsr(db: Session = Depends(get_db)) -> dict:
    try:
        record = fetch_hsr_record()
    except SyncError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    player = apply_profile_update(
        db,
        "hsr",
        ProfileUpdate(
            uid=record["uid"],
            nickname=record["nickname"],
            level=record["level"],
            active_days=record["active_days"],
            achievements=record["achievements"],
            stamina_current=record["stamina_current"],
            stamina_max=record["stamina_max"],
            characters=[CharacterIn(**c) for c in record["characters"]],
            source="sync",
        ),
    )
    return share_payload(db, player)
