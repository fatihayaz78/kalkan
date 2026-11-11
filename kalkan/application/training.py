"""Training and evaluation use cases for the screening classifier."""
from __future__ import annotations

from typing import Sequence

from sklearn.metrics import precision_recall_fscore_support

from ..adapters.classifiers.tfidf import TfidfClassifier
from ..detection.pipeline import DetectionPipeline
from ..domain.models import Decision, LabeledText
from ..domain.ports import ModelRegistry, TrainingDataSource
from .errors import Conflict
from .factory import PipelineFactory


def evaluate(pipeline: DetectionPipeline, rows: Sequence[LabeledText]) -> dict:
    if not rows:
        return {}
    y = [r.label for r in rows]
    pred = [int(pipeline.run(r.text).decision != Decision.ALLOW) for r in rows]
    p, r, f, _ = precision_recall_fscore_support(y, pred, average="binary", zero_division=0)
    benign = [pr for pr, yy in zip(pred, y) if yy == 0]
    return {"n": len(y), "precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4),
            "false_block_rate": round(sum(benign) / len(benign), 4) if benign else 0.0}


class ModelTrainer:
    def __init__(self, registry: ModelRegistry, data: TrainingDataSource, factory: PipelineFactory):
        self._registry, self._data, self._factory = registry, data, factory

    def train_new_version(self, extra: Sequence[LabeledText] = ()) -> tuple[str, dict]:
        """Train on the train split + extra rows. Never activates: an admin decides."""
        rows = self._data.split("train") + list(extra)
        if not rows:
            raise Conflict("No training data found; run scripts/build_dataset.py")
        norm = self._factory.normalizer
        clf = TfidfClassifier().fit([norm.normalize(r.text).folded for r in rows], [r.label for r in rows])
        version = self._registry.new_version()
        clf.save(self._registry.path(version))
        pipeline = self._factory.build(self._registry.path(version), version)
        metrics = {"train_rows": len(rows), "feedback_rows": len(extra),
                   "test": evaluate(pipeline, self._data.split("test")),
                   "evasion": evaluate(pipeline, self._data.split("evasion"))}
        self._registry.save_metrics(version, metrics)
        return version, metrics
