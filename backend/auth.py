"""Auth: optional demo token, local JWT, or Supabase HS256 JWT."""
from __future__ import annotations

import logging
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError

from config import get_settings

log = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)
DEMO_USER = "00000000-0000-0000-0000-000000000001"


def _decode_sub(token: str) -> str | None:
    s = get_settings()
    for secret, audience in [
        (s.jwt_secret, None),
        (s.supabase_jwt_secret, "authenticated" if s.supabase_jwt_secret else None),
    ]:
        if not secret:
            continue
        try:
            opts: dict[str, Any] = {"algorithms": ["HS256"]}
            if audience:
                try:
                    return str(
                        jwt.decode(token, secret, audience=audience, **opts).get("sub")
                    )
                except Exception:
                    pass
            return str(jwt.decode(token, secret, options={"verify_aud": False}, **opts).get("sub"))
        except PyJWTError:
            continue
    return None


async def get_user_id(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> str:
    s = get_settings()
    if not creds or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token"
        )
    token = creds.credentials.strip()
    if s.demo_mode and s.demo_bearer_token and token == s.demo_bearer_token:
        return DEMO_USER
    sub = _decode_sub(token)
    if not sub:
        log.warning("invalid jwt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )
    return sub


def issue_local_token(sub: str = DEMO_USER) -> str:
    s = get_settings()
    return jwt.encode(
        {"sub": sub, "role": "ops"},
        s.jwt_secret,
        algorithm="HS256",
    )
