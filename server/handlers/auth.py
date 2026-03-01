"""Auth HTTP handler: JWT login."""

from __future__ import annotations

from fastapi import HTTPException, Request

from server.auth import EXPIRY_SECONDS, create_token
from server.models import AuthLoginRequest


async def auth_login(request: Request, body: AuthLoginRequest) -> dict:
    """Exchange password for JWT when auth_enabled and jwt_secret are set."""
    config = request.app.state.config
    gateway = getattr(config, "gateway", None)
    enabled = getattr(gateway, "auth_enabled", False)
    secret = getattr(gateway, "jwt_secret", None) or ""
    if not enabled or not secret:
        raise HTTPException(status_code=501, detail="Auth not configured")
    if body.password != secret:
        raise HTTPException(status_code=401, detail="Invalid password")
    token = create_token(secret)
    return {"token": token, "expires_in": EXPIRY_SECONDS}
