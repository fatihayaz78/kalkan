"""File-system model registry.

models/
  v1/classical.joblib, v1/metrics.json, v1/berturk/ (optional)
  active.txt  -> "v2"
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_V = re.compile(r"^v(\d+)$")


class FileSystemModelRegistry:
    def __init__(self, root: str | Path = "models"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def versions(self) -> list[str]:
        vs = [p.name for p in self.root.iterdir() if p.is_dir() and _V.match(p.name)]
        return sorted(vs, key=lambda v: int(v[1:]))

    def active(self) -> str | None:
        f = self.root / "active.txt"
        if f.exists() and (self.root / f.read_text().strip()).is_dir():
            return f.read_text().strip()
        vs = self.versions()
        return vs[-1] if vs else None

    def path(self, version: str) -> Path:
        if not _V.match(version):
            raise ValueError(f"Invalid version: {version}")
        return self.root / version

    def new_version(self) -> str:
        vs = self.versions()
        v = f"v{int(vs[-1][1:]) + 1 if vs else 1}"
        self.path(v).mkdir()
        return v

    def activate(self, version: str) -> None:
        if not self.path(version).is_dir():
            raise KeyError(version)
        (self.root / "active.txt").write_text(version)

    def metrics(self, version: str) -> dict:
        f = self.path(version) / "metrics.json"
        return json.loads(f.read_text()) if f.exists() else {}

    def save_metrics(self, version: str, metrics: dict) -> None:
        (self.path(version) / "metrics.json").write_text(json.dumps(metrics, indent=2))
