"""
Optional JWT authentication for REST API.

When gateway.auth_enabled is True and gateway.jwt_secret is set, protected
endpoints require Authorization: Bearer <token>. POST /auth/login with
password equal to jwt_secret returns a JWT (single-user mode).
"""

from __future__ import annotations

import time
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status

# Default algorithm
ALGORITHM = "HS256"
# Token validity (seconds)
EXPIRY_SECONDS = 7 * 24 * 3600  # 7 days


def create_token(secret: str, sub: str = "user", role: str = "admin") -> str:
    """Create a JWT with sub and role."""
    now = int(time.time())
    payload = {"sub": sub, "role": role, "iat": now, "exp": now + EXPIRY_SECONDS}
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def verify_token(secret: str, token: str) -> dict:
    """Verify and decode JWT. Raises jwt.InvalidTokenError on failure."""
    return jwt.decode(token, secret, algorithms=[ALGORITHM])


async def require_auth(request: Request) -> dict:
    """
    Dependency: require valid JWT when auth is enabled.
    Sets request.state.user from token payload (sub, role).
    """
    config = getattr(request.app.state, "config", None)
    if not config:
        return {"sub": "user", "role": "admin"}
    gateway = getattr(config, "gateway", None)
    if not gateway or not getattr(gateway, "auth_enabled", False):
        return {"sub": "user", "role": "admin"}
    secret = getattr(gateway, "jwt_secret", None) or ""
    if not secret:
        return {"sub": "user", "role": "admin"}
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    token = auth[7:].strip()
    try:
        payload = verify_token(secret, token)
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    request.state.user = payload
    return payload


# Type alias for dependency injection
AuthUser = Annotated[dict, Depends(require_auth)]
