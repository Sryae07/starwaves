"""账号体系：手机验证码注册 / 用户名（或手机号）+ 密码登录 / 退出。

开发模式说明：未接入短信服务商，验证码由 /api/auth/send-code 直接在响应里
返回 dev_code（仅本机调试使用）。生产部署时请在此文件替换为真实短信发送，
并移除 dev_code 字段。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuthToken, PhoneCode, Player, User, utcnow
from ..schemas import LoginIn, RegisterIn, SendCodeIn
from ..security import (
    hash_password,
    hash_token,
    mask_phone,
    new_sms_code,
    new_token,
    random_username,
    verify_password,
)
from .deps import get_current_user, require_api_key

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger("starwaves.auth")

CODE_TTL = timedelta(minutes=5)
SEND_COOLDOWN = timedelta(seconds=60)
MAX_ATTEMPTS = 5
TOKEN_TTL = timedelta(days=30)


def _aware(dt: datetime) -> datetime:
    """SQLite 读回的 datetime 是 naive，统一补上 UTC 时区再比较。"""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _issue_token(db: Session, user: User) -> dict:
    raw = new_token()
    expires_at = utcnow() + TOKEN_TTL
    db.add(AuthToken(token_hash=hash_token(raw), user_id=user.id, expires_at=expires_at))
    db.commit()
    return {"token": raw, "expires_at": expires_at.isoformat()}


def _user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "phone": mask_phone(user.phone) if user.phone else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "is_owner": bool(user.is_owner),
    }


@router.post("/send-code")
def send_code(payload: SendCodeIn, db: Session = Depends(get_db)) -> dict:
    now = utcnow()
    latest = (
        db.query(PhoneCode)
        .filter(PhoneCode.phone == payload.phone)
        .order_by(PhoneCode.created_at.desc())
        .first()
    )
    if (
        latest is not None
        and latest.created_at is not None
        and now - _aware(latest.created_at) < SEND_COOLDOWN
    ):
        raise HTTPException(status_code=429, detail="发送太频繁，请 60 秒后再试")

    db.query(PhoneCode).filter(PhoneCode.phone == payload.phone, PhoneCode.used.is_(False)).update(
        {PhoneCode.used: True}
    )
    code = new_sms_code()
    db.add(
        PhoneCode(
            phone=payload.phone,
            code_hash=hash_password(code),
            expires_at=now + CODE_TTL,
        )
    )
    db.commit()
    logger.info("开发模式验证码 phone=%s code=%s（生产环境请接入真实短信）", payload.phone, code)
    return {"sent": True, "expires_in": int(CODE_TTL.total_seconds()), "dev_code": code}


@router.post("/register")
def register(payload: RegisterIn, db: Session = Depends(get_db)) -> dict:
    if db.query(User).filter(User.phone == payload.phone).first() is not None:
        raise HTTPException(status_code=409, detail="该手机号已注册，请直接登录")

    row = (
        db.query(PhoneCode)
        .filter(PhoneCode.phone == payload.phone, PhoneCode.used.is_(False))
        .order_by(PhoneCode.created_at.desc())
        .first()
    )
    if row is None or _aware(row.expires_at) < utcnow():
        raise HTTPException(status_code=400, detail="验证码无效或已过期，请重新获取")
    row.attempts += 1
    if row.attempts > MAX_ATTEMPTS:
        row.used = True
        db.commit()
        raise HTTPException(status_code=400, detail="验证码错误次数过多，请重新获取")
    if not verify_password(payload.code, row.code_hash):
        db.commit()
        raise HTTPException(status_code=400, detail=f"验证码错误（还可尝试 {MAX_ATTEMPTS - row.attempts} 次）")
    row.used = True

    username = payload.username.strip()
    if not username:
        username = random_username(db)
    if db.query(User).filter(User.username == username).first() is not None:
        raise HTTPException(status_code=409, detail="该用户名已被占用，换一个试试")

    user = User(username=username, phone=payload.phone, password_hash=hash_password(payload.password))
    if db.query(User).filter_by(is_owner=True).first() is None:
        user.is_owner = True
    db.add(user)
    db.flush()
    player = Player(user_id=user.id, nickname=username)
    db.add(player)
    db.commit()
    db.refresh(user)
    token = _issue_token(db, user)
    return {"token": token["token"], "expires_at": token["expires_at"], "user": _user_payload(user), "share_id": player.share_id}


@router.post("/login")
def login(payload: LoginIn, db: Session = Depends(get_db)) -> dict:
    account = payload.account.strip()
    user = db.query(User).filter(
        (User.username == account) | (User.phone == account)
    ).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名/手机号或密码错误")
    token = _issue_token(db, user)
    return {"token": token["token"], "expires_at": token["expires_at"], "user": _user_payload(user)}


@router.post("/logout", dependencies=[Depends(require_api_key)])
def logout(
    user: User = Depends(get_current_user),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    raw = (authorization or "").removeprefix("Bearer ").strip()
    if raw:
        db.query(AuthToken).filter(AuthToken.token_hash == hash_token(raw)).delete()
        db.commit()
    return {"logout": True}
