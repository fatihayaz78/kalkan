"""Stage 4 - fine-tuned Turkish transformer (BERTurk by default).

Optional at runtime: if torch/transformers or the model directory are missing,
the cascade falls back to stage 3. Long inputs are scored in overlapping
512-token windows and the maximum window score is used, so an injection
buried inside a long retrieved document is still caught.
"""
from __future__ import annotations

from pathlib import Path


class TransformerModel:
    def __init__(self, model_dir: str | Path, max_len: int = 512, stride: int = 128):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_dir).eval()
        self.max_len, self.stride = max_len, stride

    @classmethod
    def try_load(cls, model_dir: str | Path) -> "TransformerModel | None":
        if not Path(model_dir, "config.json").exists():
            return None
        try:
            return cls(model_dir)
        except ImportError:
            return None

    def score(self, text: str) -> float:
        enc = self.tok(
            text, truncation=True, max_length=self.max_len, stride=self.stride,
            return_overflowing_tokens=True, padding=True, return_tensors="pt",
        )
        enc.pop("overflow_to_sample_mapping", None)
        with self.torch.no_grad():
            probs = self.model(**enc).logits.softmax(-1)[:, 1]
        return float(probs.max())
