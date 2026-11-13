"""留言板：公开可读，登录用户可留言。"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Message, User
from .deps import get_current_user, require_api_key

router = APIRouter(prefix="/api/messages", tags=["messages"])


@router.get("")
def list_messages(db: Session = Depends(get_db)) -> dict:
    rows = db.query(Message).order_by(Message.created_at.desc()).limit(50).all()
    items = [
        {
            "id": row.id,
            "username": row.username or "匿名",
            "content": row.content,
            "created_at": row.created_at.strftime("%m-%d %H:%M") if row.created_at else "",
        }
        for row in rows
    ]
    return {"items": items}


@router.post("", dependencies=[Depends(require_api_key)])
def create_message(
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    content = str(payload.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=422, detail="留言内容不能为空")
    if len(content) > 500:
        raise HTTPException(status_code=422, detail="留言最多 500 字")
    row = Message(user_id=user.id, username=user.username, content=content)
    db.add(row)
    db.commit()
    return {"created": True}
