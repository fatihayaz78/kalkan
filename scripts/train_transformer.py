"""Fine-tune stage 4 (BERTurk by default) on data/processed.

Needs: pip install -r requirements-train.txt  (torch, transformers, datasets).
Run on Colab or a local GPU; CPU works but is slow.

    python scripts/train_transformer.py --out models/v2/berturk
    python scripts/train_transformer.py --model FacebookAI/xlm-roberta-base --out models/v2/berturk
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def load(name):
    return [json.loads(l) for l in Path(f"data/processed/{name}.jsonl").read_text(encoding="utf-8").splitlines()]


def main():
    from datasets import Dataset
    from sklearn.metrics import f1_score, precision_score, recall_score
    from transformers import (AutoModelForSequenceClassification, AutoTokenizer, DataCollatorWithPadding,
                              Trainer, TrainingArguments, set_seed)

    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="dbmdz/bert-base-turkish-cased")
    ap.add_argument("--out", required=True, help="e.g. models/v3/berturk (a version directory + /berturk)")
    ap.add_argument("--epochs", type=float, default=3)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    set_seed(args.seed)

    tok = AutoTokenizer.from_pretrained(args.model)
    def ds(name):
        rows = load(name)
        d = Dataset.from_dict({"text": [r["text"] for r in rows], "label": [r["label"] for r in rows]})
        return d.map(lambda b: tok(b["text"], truncation=True, max_length=256), batched=True)

    train, val = ds("train"), ds("val")
    model = AutoModelForSequenceClassification.from_pretrained(args.model, num_labels=2)

    # Class weights are handled by oversampling-free weighted loss would need a custom Trainer;
    # keep it simple and rely on threshold calibration on the val split.
    def compute(p):
        pred = p.predictions.argmax(-1)
        return {"f1": f1_score(p.label_ids, pred), "precision": precision_score(p.label_ids, pred, zero_division=0),
                "recall": recall_score(p.label_ids, pred)}

    targs = TrainingArguments(
        output_dir=f"{args.out}-ckpt", num_train_epochs=args.epochs, learning_rate=args.lr,
        per_device_train_batch_size=args.batch, per_device_eval_batch_size=32, eval_strategy="epoch",
        save_strategy="epoch", load_best_model_at_end=True, metric_for_best_model="f1",
        weight_decay=0.01, warmup_ratio=0.1, seed=args.seed, report_to=[],
    )
    trainer = Trainer(model=model, args=targs, train_dataset=train, eval_dataset=val,
                      data_collator=DataCollatorWithPadding(tok), compute_metrics=compute)
    trainer.train()
    trainer.save_model(args.out)
    tok.save_pretrained(args.out)
    print(json.dumps(trainer.evaluate(), indent=2))


if __name__ == "__main__":
    main()
