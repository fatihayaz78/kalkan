"""Builds detection pipelines from a model version directory (Factory).

The only place that knows which concrete stages and classifiers make up Kalkan.
"""
from __future__ import annotations

from pathlib import Path

from ..adapters.classifiers.tfidf import TfidfClassifier
from ..adapters.classifiers.transformer import TransformerClassifier
from ..detection.normalizer import TurkishNormalizer
from ..detection.pipeline import DetectionPipeline
from ..detection.rules import RuleSet
from ..detection.stages import FOLDED, ORIGINAL, RuleStage, ScoringStage, ScreeningStage
from ..domain.ports import Normalizer


class PipelineFactory:
    def __init__(self, normalizer: Normalizer | None = None, rules: RuleSet | None = None,
                 enable_transformer: bool = True):
        self.normalizer = normalizer or TurkishNormalizer()
        self.rules = rules or RuleSet(self.normalizer)
        self._enable_transformer = enable_transformer

    def build(self, version_dir: Path | None, version: str | None = None) -> DetectionPipeline:
        stages = [RuleStage(self.rules)]
        if version_dir and TfidfClassifier.exists(version_dir):
            stages.append(ScreeningStage("classical", TfidfClassifier.load(version_dir), FOLDED))
        if version_dir and self._enable_transformer:
            if (transformer := TransformerClassifier.try_load(version_dir)) is not None:
                stages.append(ScoringStage("transformer", transformer, ORIGINAL))
        return DetectionPipeline(self.normalizer, stages, version)

    def rules_only(self) -> DetectionPipeline:
        return DetectionPipeline(self.normalizer, [RuleStage(self.rules)], "rules-only")
