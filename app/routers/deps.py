"""公共依赖：写接口鉴权。"""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException

from ..config import API_KEY


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """配置了 API_KEY 时校验 X-API-Key 请求头；未配置则放行（仅限本机调试）。"""
    if API_KEY is None:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="API Key 缺失或无效（请求头 X-API-Key）")
