"""Per-client policy resolution (Strategy: each client may get different thresholds)."""
from __future__ import annotations

from typing import Mapping

from ..domain.models import Policy


class ClientPolicies:
    def __init__(self, overrides: Mapping[str, Mapping[str, float]] | None = None, base: Policy | None = None):
        overrides = dict(overrides or {})
        self._base = (base or Policy()).with_overrides(overrides.pop("default", None))
        self._overrides = overrides

    def for_client(self, client: str) -> Policy:
        return self._base.with_overrides(self._overrides.get(client))
