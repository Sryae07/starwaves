"""账号安全：密码散列、会话令牌、手机验证码（开发模式模拟短信）。"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import string

from sqlalchemy.orm import Session

_PBKDF2_ROUNDS = 120_000


def hash_password(password: str) -> str:
    """PBKDF2-HMAC-SHA256，随机盐，格式 pbkdf2$rounds$salt$digest。"""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2${_PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _algo, rounds, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def new_sms_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def random_username(db: Session, prefix: str = "用户") -> str:
    """默认用户名：用户 + 随机不重复编号（唯一性由 users.username 约束兜底）。"""
    from .models import User

    for digits in (6, 8, 10):
        for _ in range(20):
            number = secrets.randbelow(10**digits - 10 ** (digits - 1)) + 10 ** (digits - 1)
            candidate = f"{prefix}{number}"
            if db.query(User).filter(User.username == candidate).first() is None:
                return candidate
    suffix = "".join(secrets.choice(string.digits) for _ in range(12))
    return f"{prefix}{suffix}"


def mask_phone(phone: str) -> str:
    if len(phone) == 11 and phone.isdigit():
        return f"{phone[:3]}****{phone[-4:]}"
    return phone
