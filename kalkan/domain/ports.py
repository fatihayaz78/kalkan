"""Ports: the interfaces the application depends on (Dependency Inversion).

Concrete implementations live in kalkan.adapters; the composition root
(kalkan.api.app) wires them together.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, Sequence, runtime_checkable

from .models import AuditRecord, LabeledText, NormalizedText, Policy, StageResult


class Normalizer(Protocol):
    def normalize(self, text: str) -> NormalizedText: ...


class TextClassifier(Protocol):
    """Anything that returns an injection probability per text."""
    def score(self, texts: Sequence[str]) -> list[float]: ...


@runtime_checkable
class TrainableClassifier(TextClassifier, Protocol):
    def fit(self, texts: Sequence[str], labels: Sequence[int]) -> "TrainableClassifier": ...
    def save(self, directory: Path) -> None: ...


class DetectionContext(Protocol):
    text: str
    normalized: NormalizedText
    policy: Policy


class DetectionStage(Protocol):
    """One link in the detection chain (Chain of Responsibility)."""
    name: str

    def evaluate(self, ctx: DetectionContext) -> StageResult: ...


class ModelRegistry(Protocol):
    def versions(self) -> list[str]: ...
    def active(self) -> str | None: ...
    def path(self, version: str) -> Path: ...
    def new_version(self) -> str: ...
    def activate(self, version: str) -> None: ...
    def metrics(self, version: str) -> dict: ...
    def save_metrics(self, version: str, metrics: dict) -> None: ...


class AuditLog(Protocol):
    def record(self, entry: AuditRecord) -> None: ...
    def text_of(self, request_id: str) -> str | None: ...
    def stats(self, since_seconds: float) -> dict: ...


class FeedbackRepository(Protocol):
    def add(self, client: str, request_id: str | None, text: str, label: int, note: str | None) -> int: ...
    def list(self, status: str | None = None, limit: int = 200) -> list[dict]: ...
    def review(self, feedback_id: int, status: str, label: int | None) -> bool: ...
    def pending_count(self) -> int: ...


class TrainingDataSource(Protocol):
    def split(self, name: str) -> list[LabeledText]: ...


class AttackGenerator(Protocol):
    """Produces variants of an attack for red-team runs."""
    def variants(self, attack: str, n: int) -> list[str]: ...
