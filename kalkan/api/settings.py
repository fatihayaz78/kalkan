"""Service settings from environment variables (12-factor; no config file required)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


def parse_keys(raw: str) -> dict[str, str]:
    """'chatbot-a:secret1,chatbot-b:secret2' -> {secret1: chatbot-a, ...}"""
    out = {}
    for pair in filter(None, (p.strip() for p in raw.split(","))):
        name, _, key = pair.partition(":")
        if not key:
            raise ValueError(f"KALKAN_API_KEYS entry '{pair}' must be name:key")
        out[key] = name
    return out


def _policies() -> dict:
    p = os.getenv("KALKAN_POLICIES")
    return json.loads(Path(p).read_text()) if p and Path(p).exists() else {}


@dataclass
class Settings:
    models_dir: Path = field(default_factory=lambda: Path(os.getenv("KALKAN_MODELS_DIR", "models")))
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("KALKAN_DATA_DIR", "data/processed")))
    db_path: Path = field(default_factory=lambda: Path(os.getenv("KALKAN_DB", "data/kalkan.db")))
    api_keys: dict[str, str] = field(default_factory=lambda: parse_keys(os.getenv("KALKAN_API_KEYS", "")))
    admin_key: str = field(default_factory=lambda: os.getenv("KALKAN_ADMIN_KEY", ""))
    policies: dict = field(default_factory=_policies)
    log_text: str = field(default_factory=lambda: os.getenv("KALKAN_LOG_TEXT", "flagged"))
    max_chars: int = field(default_factory=lambda: int(os.getenv("KALKAN_MAX_CHARS", "32000")))
    max_batch: int = field(default_factory=lambda: int(os.getenv("KALKAN_MAX_BATCH", "64")))

    @property
    def auth_enabled(self) -> bool:
        return bool(self.api_keys)
