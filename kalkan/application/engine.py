"""Holds the live detection pipeline and swaps it atomically when a new version is activated."""
from __future__ import annotations

import threading

from ..detection.pipeline import DetectionPipeline
from ..domain.ports import ModelRegistry
from .errors import NotFound
from .factory import PipelineFactory


class EngineProvider:
    def __init__(self, registry: ModelRegistry, factory: PipelineFactory):
        self._registry, self._factory = registry, factory
        self._lock = threading.Lock()
        self._pipeline = self._load(registry.active())

    def _load(self, version: str | None) -> DetectionPipeline:
        return self._factory.build(self._registry.path(version) if version else None, version)

    @property
    def current(self) -> DetectionPipeline:
        return self._pipeline

    def activate(self, version: str) -> None:
        try:
            self._registry.activate(version)
        except (KeyError, ValueError):
            raise NotFound(f"unknown model version {version}")
        pipeline = self._load(version)
        with self._lock:
            self._pipeline = pipeline
