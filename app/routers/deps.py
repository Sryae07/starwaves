"""公共依赖：写接口鉴权（Bearer 登录态 + 可选 API Key）。"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..config import API_KEY
from ..database import get_db
from ..models import AuthToken, User
from ..security import hash_token


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """配置了 API_KEY 时校验 X-API-Key 请求头；未配置则放行（仅限本机调试）。"""
    if API_KEY is None:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="API Key 缺失或无效（请求头 X-API-Key）")


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """从 Authorization: Bearer <token> 解析登录用户。"""
    raw = (authorization or "").removeprefix("Bearer ").strip()
    if not raw:
        raise HTTPException(status_code=401, detail="请先登录")
    row = db.query(AuthToken).filter(AuthToken.token_hash == hash_token(raw)).first()
    if row is None:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    if row.expires_at is not None and _aware(row.expires_at) < datetime.now(timezone.utc):
        db.delete(row)
        db.commit()
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return row.user
