"""卡片截图存放：每个登录用户、每个游戏卡片各自一个相册。"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import GALLERY_DIR
from ..database import get_db
from ..games import merged_games
from ..models import Screenshot, User
from .deps import get_current_user, require_api_key

router = APIRouter(prefix="/api/gallery", tags=["gallery"])

THUMB_DIR = GALLERY_DIR / "thumbs"
ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
MAX_SIZE = 20 * 1024 * 1024
IMG_RE = r"^[a-f0-9]{32}\.(png|jpg|jpeg|webp|gif)$"


def _make_thumb(src_path: Path, filename: str) -> str:
    """生成 480px 缩略图（JPEG），失败时返回空串（列表回退用原图）。"""
    try:
        from PIL import Image

        THUMB_DIR.mkdir(parents=True, exist_ok=True)
        thumb_path = THUMB_DIR / f"{Path(filename).stem}.jpg"
        with Image.open(src_path) as im:
            im.thumbnail((480, 480))
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            im.save(thumb_path, "JPEG", quality=80)
        return thumb_path.name
    except Exception:
        return ""


def _items(db: Session, user: User, game: str) -> list[dict]:
    rows = (
        db.query(Screenshot)
        .filter(Screenshot.user_id == user.id, Screenshot.game == game)
        .order_by(Screenshot.created_at.desc())
        .all()
    )
    return [
        {
            "id": row.id,
            "url": f"/api/gallery/img/{row.filename}",
            "thumb": f"/api/gallery/thumb/{row.filename}",
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.post("/{game}", dependencies=[Depends(require_api_key)])
async def upload_screenshot(
    game: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    registry = merged_games(db)
    if game not in registry:
        raise HTTPException(status_code=404, detail=f"未知游戏: {game}")
    ext = Path(file.filename or "shot.png").suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=415, detail=f"仅支持图片格式: {', '.join(sorted(ALLOWED_EXTS))}")
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="图片超过 20MB 上限")
    folder = GALLERY_DIR / str(user.id) / game
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    src_path = folder / filename
    src_path.write_bytes(content)
    _make_thumb(src_path, filename)
    db.add(Screenshot(user_id=user.id, game=game, filename=filename))
    db.commit()
    return {"uploaded": True, "count": len(_items(db, user, game)), "items": _items(db, user, game)}


@router.get("/{game}", dependencies=[Depends(require_api_key)])
def list_screenshots(
    game: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    registry = merged_games(db)
    if game not in registry:
        raise HTTPException(status_code=404, detail=f"未知游戏: {game}")
    items = _items(db, user, game)
    return {"game": game, "count": len(items), "items": items}


@router.delete("/{game}/{image_id}", dependencies=[Depends(require_api_key)])
def delete_screenshot(
    game: str,
    image_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    row = (
        db.query(Screenshot)
        .filter(Screenshot.id == image_id, Screenshot.user_id == user.id, Screenshot.game == game)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="截图不存在或无权删除")
    (GALLERY_DIR / str(user.id) / game / row.filename).unlink(missing_ok=True)
    (THUMB_DIR / f"{Path(row.filename).stem}.jpg").unlink(missing_ok=True)
    db.delete(row)
    db.commit()
    return {"deleted": True, "count": len(_items(db, user, game))}


@router.get("/thumb/{filename}")
def serve_thumb(filename: str) -> FileResponse:
    import re

    if not re.fullmatch(IMG_RE, filename):
        raise HTTPException(status_code=404, detail="无效图片")
    thumb = THUMB_DIR / f"{Path(filename).stem}.jpg"
    if not thumb.exists():
        matches = list(GALLERY_DIR.glob(f"*/*/{filename}"))
        if not matches:
            raise HTTPException(status_code=404, detail="图片不存在")
        return FileResponse(matches[0], media_type="image/jpeg")
    return FileResponse(thumb, media_type="image/jpeg")


@router.get("/img/{filename}")
def serve_image(filename: str) -> FileResponse:
    import re

    if not re.fullmatch(IMG_RE, filename):
        raise HTTPException(status_code=404, detail="无效图片")
    matches = list(GALLERY_DIR.glob(f"*/*/{filename}"))
    if not matches:
        raise HTTPException(status_code=404, detail="图片不存在")
    ext = matches[0].suffix.lower()
    media = {"gif": "image/gif", "png": "image/png", "webp": "image/webp"}.get(ext[1:], "image/jpeg")
    return FileResponse(matches[0], media_type=media)
