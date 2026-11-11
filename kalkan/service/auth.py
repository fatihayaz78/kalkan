"""API-key auth. Clients send `Authorization: Bearer <key>` or `X-API-Key: <key>`.

No keys configured -> dev mode: every request is client "dev" (shown in /health).
"""
from __future__ import annotations

import hmac

from fastapi import HTTPException, Request


def _presented(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("x-api-key", "").strip()


def client_name(request: Request) -> str:
    s = request.app.state.settings
    if not s.auth_enabled:
        return "dev"
    key = _presented(request)
    for known, name in s.api_keys.items():
        if hmac.compare_digest(key, known):
            return name
    raise HTTPException(401, "Missing or invalid API key. Send 'Authorization: Bearer <key>'.")


def require_admin(request: Request) -> str:
    s = request.app.state.settings
    if not s.admin_key:
        if s.auth_enabled:
            raise HTTPException(403, "Admin API is disabled: set KALKAN_ADMIN_KEY.")
        return "dev-admin"
    if not hmac.compare_digest(_presented(request), s.admin_key):
        raise HTTPException(401, "Admin key required.")
    return "admin"
