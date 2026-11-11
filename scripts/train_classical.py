"""Train a new screening-model version into models/ and activate it.

    python scripts/train_classical.py               # train + activate
    python scripts/train_classical.py --no-activate
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kalkan.adapters.data.jsonl import JsonlDataSource  # noqa: E402
from kalkan.adapters.registry.filesystem import FileSystemModelRegistry  # noqa: E402
from kalkan.application.factory import PipelineFactory  # noqa: E402
from kalkan.application.training import ModelTrainer  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="models")
    ap.add_argument("--data", default="data/processed")
    ap.add_argument("--no-activate", action="store_true")
    args = ap.parse_args()
    registry = FileSystemModelRegistry(args.models)
    version, metrics = ModelTrainer(registry, JsonlDataSource(args.data), PipelineFactory()).train_new_version()
    if not args.no_activate:
        registry.activate(version)
    print(json.dumps({"version": version, "active": not args.no_activate, **metrics}, indent=2))
