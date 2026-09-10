"""
API-key authentication for the HTTP API.

What this file used to be: a JWT scheme over an in-memory ``users_db`` dict.
Anyone could ``POST /api/v1/auth/register`` (there was no admin gate), the
store vanished on restart, tokens were signed with ``SECRET_KEY`` defaulting to
``"dev-secret-key"``, and not one agent route depended on it -- only
``/api/v1/auth/me`` did. It protected nothing and read as though it did.

Every ``/api/v1`` route now depends on ``require_api_key``: one shared key in
the ``X-API-Key`` header, compared in constant time. Production refuses to start
while the key is the placeholder (``src.config``). Per-user identity is a
documented limit, not a half-built feature. See ADR 0003.
"""

from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from src.config import get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str | None = Depends(api_key_header)) -> str:
    """Dependency: reject the request unless the configured key is presented."""
    expected = get_settings().api_key
    if not api_key or not secrets.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "X-API-Key"},
        )
    return api_key
