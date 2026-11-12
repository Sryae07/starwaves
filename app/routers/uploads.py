"""截图上传 + OCR 识别。

两段式设计：
1. 只上传不保存 -> 返回 OCR 原始文本和解析结果，前端展示可编辑表单；
2. 用户核对修正后，通过 /api/profiles/{game} 确认入库。
apply=true 时跳过校对直接入库（默认关闭，建议保留人工核对）。
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import UPLOAD_DIR
from ..database import get_db
from ..games import merged_games
from ..schemas import ProfileUpdate
from ..services.ocr import OcrUnavailable, ocr_image
from ..services.parser import parse_ocr_text
from ..services.profiles import apply_profile_update
from ..services.serializers import share_payload
from .deps import require_api_key

router = APIRouter(prefix="/api", tags=["upload"])
ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_SIZE = 10 * 1024 * 1024


def _to_profile_update(game: str, parsed: dict, source: str, registry: dict) -> ProfileUpdate:
    return ProfileUpdate(
        uid=parsed.get("uid") or "",
        level=parsed.get("level") or 0,
        active_days=parsed.get("active_days") or 0,
        achievements=parsed.get("achievements") or 0,
        stamina_current=parsed.get("stamina_current") or 0,
        stamina_max=parsed.get("stamina_max") or registry[game].cap,
        source=source,
    )


@router.post("/upload/{game}", dependencies=[Depends(require_api_key)])
async def upload_screenshot(
    game: str,
    file: UploadFile = File(...),
    apply: bool = Form(False),
    db: Session = Depends(get_db),
) -> dict:
    registry = merged_games(db)
    if game not in registry:
        raise HTTPException(status_code=404, detail=f"未知游戏: {game}，支持: {', '.join(registry)}")
    ext = Path(file.filename or "shot.png").suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=415, detail=f"仅支持图片格式: {', '.join(sorted(ALLOWED_EXTS))}")
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="图片超过 10MB 上限")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    dest.write_bytes(content)

    try:
        ocr_text = ocr_image(dest)
    except OcrUnavailable as exc:
        raise HTTPException(status_code=501, detail=str(exc))

    parsed = parse_ocr_text(ocr_text, game, registry)
    saved = None
    if apply:
        if parsed.get("level") is None and parsed.get("stamina_current") is None:
            raise HTTPException(
                status_code=422,
                detail="OCR 未识别出关键数值（等级/体力），请换截图重试或改用手动录入",
            )
        player = apply_profile_update(db, game, _to_profile_update(game, parsed, "ocr", registry))
        saved = share_payload(db, player)
    return {"saved": apply, "ocr_text": ocr_text, "parsed": parsed, "profile": saved}
