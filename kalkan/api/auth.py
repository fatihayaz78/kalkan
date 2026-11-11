"""API-key authentication. Clients send `Authorization: Bearer <key>` or `X-API-Key: <key>`.

No client keys configured -> dev mode: every request is client "dev".
"""
from __future__ import annotations

import hmac

from fastapi import HTTPException, Request


def _presented(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("x-api-key", "").strip()


class ApiKeyAuthenticator:
    def __init__(self, client_keys: dict[str, str], admin_key: str):
        self._clients, self._admin = client_keys, admin_key

    @property
    def enabled(self) -> bool:
        return bool(self._clients)

    def client(self, request: Request) -> str:
        if not self._clients:
            return "dev"
        key = _presented(request)
        for known, name in self._clients.items():
            if hmac.compare_digest(key, known):
                return name
        raise HTTPException(401, "Missing or invalid API key. Send 'Authorization: Bearer <key>'.")

    def admin(self, request: Request) -> str:
        if not self._admin:
            if self._clients:
                raise HTTPException(403, "Admin API is disabled: set KALKAN_ADMIN_KEY.")
            return "dev-admin"
        if not hmac.compare_digest(_presented(request), self._admin):
            raise HTTPException(401, "Admin key required.")
        return "admin"


def client_name(request: Request) -> str:
    return request.app.state.container.auth.client(request)


def require_admin(request: Request) -> str:
    return request.app.state.container.auth.admin(request)
