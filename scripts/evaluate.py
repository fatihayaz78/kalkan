"""Compare Kalkan with simple baselines on the test, evasion and indirect splits.

    python scripts/evaluate.py
    python scripts/evaluate.py --hf protectai/deberta-v3-base-prompt-injection-v2
Writes results/metrics.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score, precision_recall_fscore_support

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kalkan import Decision, Kalkan  # noqa: E402
from kalkan.adapters.data.jsonl import JsonlDataSource  # noqa: E402
from kalkan.application.factory import PipelineFactory  # noqa: E402

KEYWORDS = ["talimat", "yok say", "unut", "ignore", "sistem mesaj", "kural"]


def keyword_baseline(texts):
    return [float(any(k in t.lower() for k in KEYWORDS)) for t in texts]


def hf_baseline(model_id: str):
    from transformers import pipeline
    clf = pipeline("text-classification", model=model_id, truncation=True, max_length=512)

    def run(texts):
        out = []
        for r in clf(texts, batch_size=16):
            bad = any(k in r["label"].lower() for k in ("injection", "jailbreak", "unsafe", "label_1"))
            out.append(r["score"] if bad else 1 - r["score"])
        return out
    return run


def metrics(y, scores) -> dict:
    y, s = np.array(y), np.array(scores)
    pred = (s >= 0.5).astype(int)
    p, r, f, _ = precision_recall_fscore_support(y, pred, average="binary", zero_division=0)
    benign = y == 0
    res = {"n": int(len(y)), "precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4),
           "false_block_rate": round(float(pred[benign].mean()), 4) if benign.any() else None}
    if len(set(y)) == 2:
        res["pr_auc"] = round(float(average_precision_score(y, s)), 4)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hf", nargs="*", default=[], help="Hugging Face guard models to compare")
    ap.add_argument("--data", default="data/processed")
    args = ap.parse_args()

    guard = Kalkan.from_directory()
    rules_only = PipelineFactory().rules_only()
    systems = {
        "keyword": keyword_baseline,
        "rules_only": lambda ts: [float(rules_only.run(t).decision == Decision.BLOCK) for t in ts],
        "kalkan": lambda ts: [float(guard.check(t).decision != Decision.ALLOW) for t in ts],
        **{m: hf_baseline(m) for m in args.hf},
    }
    data, results = JsonlDataSource(args.data), {}
    for split in ["test", "evasion", "indirect"]:
        rows = data.split(split)
        if rows:
            texts, y = [r.text for r in rows], [r.label for r in rows]
            results[split] = {name: metrics(y, fn(texts)) for name, fn in systems.items()}
    lat = [guard.check(r.text).latency_ms for r in data.split("test")[:500]]
    if lat:
        results["latency_ms"] = {"p50": round(float(np.percentile(lat, 50)), 2),
                                 "p95": round(float(np.percentile(lat, 95)), 2)}

    Path("results").mkdir(exist_ok=True)
    Path("results/metrics.json").write_text(json.dumps(results, indent=2))
    for split, by in results.items():
        if split == "latency_ms":
            print(f"\nlatency  {by}")
            continue
        print(f"\n== {split}")
        for name, m in by.items():
            print(f"  {name:12s} P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f} "
                  f"benign_blocked={m['false_block_rate']}")


if __name__ == "__main__":
    main()
