"""Service settings from environment variables (12-factor; no config file required)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


def _keys(raw: str) -> dict[str, str]:
    """'chatbot-a:secret1,chatbot-b:secret2' -> {secret1: chatbot-a, ...}"""
    out = {}
    for pair in filter(None, (p.strip() for p in raw.split(","))):
        name, _, key = pair.partition(":")
        if not key:
            raise ValueError(f"KALKAN_API_KEYS entry '{pair}' must be name:key")
        out[key] = name
    return out


@dataclass
class Settings:
    models_dir: Path = Path(os.getenv("KALKAN_MODELS_DIR", "models"))
    data_dir: Path = Path(os.getenv("KALKAN_DATA_DIR", "data/processed"))
    db_path: Path = Path(os.getenv("KALKAN_DB", "data/kalkan.db"))
    api_keys: dict[str, str] = field(default_factory=lambda: _keys(os.getenv("KALKAN_API_KEYS", "")))
    admin_key: str = os.getenv("KALKAN_ADMIN_KEY", "")
    # Per-client policy overrides, e.g. {"chatbot-a": {"block_at": 0.7}}; "default" applies to all.
    policies: dict = field(default_factory=lambda: json.loads(Path(p).read_text())
                           if (p := os.getenv("KALKAN_POLICIES")) and Path(p).exists() else {})
    log_text: str = os.getenv("KALKAN_LOG_TEXT", "flagged")  # none | flagged | all
    max_chars: int = int(os.getenv("KALKAN_MAX_CHARS", "32000"))
    max_batch: int = int(os.getenv("KALKAN_MAX_BATCH", "64"))

    @property
    def auth_enabled(self) -> bool:
        return bool(self.api_keys)

    def policy_for(self, client: str) -> dict:
        return {**self.policies.get("default", {}), **self.policies.get(client, {})}
