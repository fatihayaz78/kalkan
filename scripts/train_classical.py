"""Train a new stage-3 model version into models/ and activate it.

    python scripts/train_classical.py            # train + activate
    python scripts/train_classical.py --no-activate
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kalkan.registry import ModelRegistry  # noqa: E402
from kalkan.training import train_new_version  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-activate", action="store_true")
    args = ap.parse_args()
    reg = ModelRegistry("models")
    version, metrics = train_new_version(reg)
    if not args.no_activate:
        reg.activate(version)
    print(f"{version} {'(active)' if not args.no_activate else ''}\n{json.dumps(metrics, indent=2)}")
