"""站点设置：自定义背景图（上传 / 恢复默认）+ 米游社 Cookie（本地数据库）。"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import DATA_DIR
from ..database import get_db
from ..models import SiteSetting
from .deps import get_current_user, require_api_key

router = APIRouter(prefix="/api", tags=["settings"])

ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_SIZE = 15 * 1024 * 1024
BG_STEM = "background"
COOKIE_KEY = "hoyolab_cookie"


class CookieIn(BaseModel):
    cookie: str = ""


def _current_background() -> Path | None:
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        candidate = DATA_DIR / f"{BG_STEM}{ext}"
        if candidate.is_file():
            return candidate
    return None


@router.get("/background")
def get_background() -> FileResponse:
    path = _current_background()
    if path is None:
        raise HTTPException(status_code=404, detail="未设置自定义背景")
    media = "image/jpeg" if path.suffix in (".jpg", ".jpeg") else "image/png"
    return FileResponse(path, media_type=media)


@router.post("/background", dependencies=[Depends(require_api_key), Depends(get_current_user)])
async def upload_background(file: UploadFile = File(...)) -> dict:
    ext = Path(file.filename or "bg.jpg").suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=415, detail=f"仅支持图片格式: {', '.join(sorted(ALLOWED_EXTS))}")
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="图片超过 15MB 上限")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for old in DATA_DIR.glob(f"{BG_STEM}.*"):
        old.unlink(missing_ok=True)
    (DATA_DIR / f"{BG_STEM}{ext}").write_bytes(content)
    return {"background": True, "url": "/api/background"}


@router.delete("/background", dependencies=[Depends(require_api_key), Depends(get_current_user)])
def reset_background() -> dict:
    for old in DATA_DIR.glob(f"{BG_STEM}.*"):
        old.unlink(missing_ok=True)
    return {"background": False}


@router.get("/settings/hoyolab-cookie", dependencies=[Depends(require_api_key), Depends(get_current_user)])
def get_hoyolab_cookie(db: Session = Depends(get_db)) -> dict:
    row = db.query(SiteSetting).filter(SiteSetting.key == COOKIE_KEY).first()
    value = row.value if row else ""
    tail = value[-8:] if value else ""
    return {"configured": bool(value), "tail": tail, "value": value}


@router.put("/settings/hoyolab-cookie", dependencies=[Depends(require_api_key), Depends(get_current_user)])
def set_hoyolab_cookie(payload: CookieIn, db: Session = Depends(get_db)) -> dict:
    value = payload.cookie.strip()
    row = db.query(SiteSetting).filter(SiteSetting.key == COOKIE_KEY).first()
    if row is None:
        db.add(SiteSetting(key=COOKIE_KEY, value=value))
    else:
        row.value = value
    db.commit()
    return {"configured": bool(value), "tail": value[-8:] if value else ""}
