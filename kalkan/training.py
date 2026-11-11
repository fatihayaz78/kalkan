"""Train and evaluate stage-3 models into the registry (used by CLI and the admin API)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.metrics import precision_recall_fscore_support

from .cascade import Kalkan
from .classical import ClassicalModel
from .registry import ModelRegistry


def load_jsonl(path: str | Path) -> list[dict]:
    p = Path(path)
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def evaluate(engine: Kalkan, rows: list[dict]) -> dict:
    if not rows:
        return {}
    y = np.array([r["label"] for r in rows])
    pred = np.array([engine.check(r["text"]).decision != "allow" for r in rows], dtype=int)
    p, r, f, _ = precision_recall_fscore_support(y, pred, average="binary", zero_division=0)
    benign = y == 0
    return {"n": int(len(y)), "precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4),
            "false_block_rate": round(float(pred[benign].mean()) if benign.any() else 0.0, 4)}


def train_new_version(registry: ModelRegistry, data_dir: str | Path = "data/processed",
                      extra_rows: list[dict] | None = None) -> tuple[str, dict]:
    """Train a new version on train split + extra rows (e.g. accepted feedback). Does NOT activate it."""
    data_dir = Path(data_dir)
    rows = load_jsonl(data_dir / "train.jsonl") + list(extra_rows or [])
    if not rows:
        raise FileNotFoundError(f"No training data in {data_dir}; run scripts/build_dataset.py")
    model = ClassicalModel.train([r["text"] for r in rows], [int(r["label"]) for r in rows])
    version = registry.new_version()
    model.save(registry.path(version) / "classical.joblib")
    engine = Kalkan(registry.path(version), version)
    metrics = {"train_rows": len(rows), "feedback_rows": len(extra_rows or []),
               "test": evaluate(engine, load_jsonl(data_dir / "test.jsonl")),
               "evasion": evaluate(engine, load_jsonl(data_dir / "evasion.jsonl"))}
    registry.save_metrics(version, metrics)
    return version, metrics
