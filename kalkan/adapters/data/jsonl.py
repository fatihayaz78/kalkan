"""JSON Lines training data source: data/processed/{train,val,test,evasion,indirect}.jsonl."""
from __future__ import annotations

import json
from pathlib import Path

from ...domain.models import LabeledText


class JsonlDataSource:
    def __init__(self, directory: str | Path):
        self._dir = Path(directory)

    def split(self, name: str) -> list[LabeledText]:
        p = self._dir / f"{name}.jsonl"
        if not p.exists():
            return []
        rows = (json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip())
        return [LabeledText(r["text"], int(r["label"])) for r in rows]
