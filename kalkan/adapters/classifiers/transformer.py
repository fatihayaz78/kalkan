"""Hugging Face sequence-classification adapter (fine-tuned BERTurk by default).

Optional: requires torch + transformers. Long inputs are scored in overlapping
512-token windows and the maximum window score is used, so an injection buried
in a long document is still caught.
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

DIRNAME = "berturk"


class TransformerClassifier:
    def __init__(self, model_dir: Path, max_len: int = 512, stride: int = 128):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._torch = torch
        self._tok = AutoTokenizer.from_pretrained(model_dir)
        self._model = AutoModelForSequenceClassification.from_pretrained(model_dir).eval()
        self._max_len, self._stride = max_len, stride

    @classmethod
    def try_load(cls, version_dir: Path) -> "TransformerClassifier | None":
        d = Path(version_dir) / DIRNAME
        if not (d / "config.json").exists():
            return None
        try:
            return cls(d)
        except ImportError:
            return None

    def score(self, texts: Sequence[str]) -> list[float]:
        return [self._score_one(t) for t in texts]

    def _score_one(self, text: str) -> float:
        enc = self._tok(text, truncation=True, max_length=self._max_len, stride=self._stride,
                        return_overflowing_tokens=True, padding=True, return_tensors="pt")
        enc.pop("overflow_to_sample_mapping", None)
        with self._torch.no_grad():
            return float(self._model(**enc).logits.softmax(-1)[:, 1].max())
