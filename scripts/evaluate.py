"""Evaluate Kalkan and baselines on test / evasion / indirect splits.

Reports precision, recall, F1, PR-AUC, recall at 1% FPR and attack success
rate (ASR = share of injections that were allowed). Writes results/metrics.json.

    python scripts/evaluate.py                     # Kalkan + keyword baseline
    python scripts/evaluate.py --hf protectai/deberta-v3-base-prompt-injection-v2
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score, precision_recall_fscore_support, roc_curve

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kalkan import Kalkan  # noqa: E402
from kalkan.normalize import normalize  # noqa: E402

KEYWORDS = ["talimat", "yok say", "unut", "ignore", "sistem mesaj", "kural"]


def load(name: str) -> list[dict]:
    p = Path("data/processed") / f"{name}.jsonl"
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def keyword_baseline(texts):
    return [float(any(k in t.lower() for k in KEYWORDS)) for t in texts]


def hf_baseline(model_id: str):
    from transformers import pipeline
    clf = pipeline("text-classification", model=model_id, truncation=True, max_length=512)

    def run(texts):
        out = []
        for r in clf(texts, batch_size=16):
            lab = r["label"].lower()
            bad = any(k in lab for k in ("injection", "jailbreak", "unsafe", "label_1"))
            out.append(r["score"] if bad else 1 - r["score"])
        return out
    return run


def metrics(y, scores, threshold=0.5) -> dict:
    y, s = np.array(y), np.array(scores)
    pred = (s >= threshold).astype(int)
    p, r, f, _ = precision_recall_fscore_support(y, pred, average="binary", zero_division=0)
    res = {"n": int(len(y)), "precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4),
           "asr": round(float(((pred == 0) & (y == 1)).sum() / max((y == 1).sum(), 1)), 4)}
    if len(set(y)) == 2:
        res["pr_auc"] = round(float(average_precision_score(y, s)), 4)
        fpr, tpr, _ = roc_curve(y, s)
        res["recall_at_1pct_fpr"] = round(float(tpr[fpr <= 0.01].max()), 4)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hf", nargs="*", default=[], help="Hugging Face guard models to compare")
    args = ap.parse_args()

    k = Kalkan.from_registry()
    systems = {
        "keyword": keyword_baseline,
        "kalkan": lambda ts: [k.check(t).score for t in ts],
    }
    if k.classical:
        systems["kalkan_no_normaliser"] = lambda ts: k.classical.score([t.lower() for t in ts])
        systems["classical_only"] = lambda ts: k.classical.score([normalize(t).folded for t in ts])
    for m in args.hf:
        systems[m] = hf_baseline(m)

    results = {}
    for split in ["test", "evasion", "indirect"]:
        rows = load(split)
        if not rows:
            continue
        texts, y = [r["text"] for r in rows], [r["label"] for r in rows]
        results[split] = {name: metrics(y, fn(texts)) for name, fn in systems.items()}

    lat = [k.check(r["text"]).latency_ms for r in load("test")[:500]]
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
            print(f"  {name:24s} P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f} "
                  f"ASR={m['asr']:.3f} R@1%FPR={m.get('recall_at_1pct_fpr', float('nan')):.3f}")


if __name__ == "__main__":
    main()
