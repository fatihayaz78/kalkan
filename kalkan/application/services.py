"""Use-case services. The API is a thin adapter over these (Facade over the application)."""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from typing import Sequence

from ..domain.models import AuditRecord, Decision, LabeledText, Source, Verdict
from ..domain.ports import AuditLog, FeedbackRepository, ModelRegistry
from .engine import EngineProvider
from .errors import Conflict, InvalidRequest, NotFound, PayloadTooLarge
from .policies import ClientPolicies
from .training import ModelTrainer

UNTRUSTED_ROLES = {"user": Source.USER, "tool": Source.TOOL, "document": Source.DOCUMENT}
LABELS = {"injection": 1, "benign": 0}


@dataclass(frozen=True)
class CheckOutcome:
    request_id: str
    verdict: Verdict


@dataclass(frozen=True)
class MessageOutcome:
    index: int
    role: str
    outcome: CheckOutcome


class GuardService:
    """Detection use cases for consuming applications."""

    def __init__(self, engine: EngineProvider, audit: AuditLog, feedback: FeedbackRepository,
                 policies: ClientPolicies, max_chars: int = 32_000, max_batch: int = 64):
        self._engine, self._audit, self._feedback = engine, audit, feedback
        self._policies, self._max_chars, self._max_batch = policies, max_chars, max_batch

    def check(self, client: str, text: str, source: Source = Source.USER) -> CheckOutcome:
        if len(text) > self._max_chars:
            raise PayloadTooLarge(f"text exceeds {self._max_chars} characters; split long documents")
        verdict = self._engine.current.run(text, self._policies.for_client(client))
        rid = uuid.uuid4().hex
        self._audit.record(AuditRecord(rid, client, source, verdict, text))
        return CheckOutcome(rid, verdict)

    def check_many(self, client: str, items: Sequence[tuple[str, Source]]) -> list[CheckOutcome]:
        if len(items) > self._max_batch:
            raise PayloadTooLarge(f"max {self._max_batch} items per batch")
        return [self.check(client, text, source) for text, source in items]

    def check_messages(self, client: str, messages: Sequence[tuple[str, str]],
                       latest_only: bool = True) -> tuple[Decision, list[MessageOutcome]]:
        """Check an OpenAI-style transcript; only untrusted roles are checked."""
        indexed = list(enumerate(messages))
        if latest_only:
            last_assistant = max((i for i, (role, _) in indexed if role == "assistant"), default=-1)
            indexed = [(i, m) for i, m in indexed if i > last_assistant]
        results = [MessageOutcome(i, role, self.check(client, content, UNTRUSTED_ROLES[role]))
                   for i, (role, content) in indexed if role in UNTRUSTED_ROLES]
        return Decision.most_severe(r.outcome.verdict.decision for r in results), results

    def report(self, client: str, label: str, request_id: str | None = None, text: str | None = None,
               note: str | None = None) -> int:
        text = text or (self._audit.text_of(request_id) if request_id else None)
        if not text:
            raise InvalidRequest("Send `text`, or a `request_id` whose text was logged.")
        return self._feedback.add(client, request_id, text, LABELS[label], note)


class AdminService:
    """Operator use cases: review reports, retrain, activate models, stats."""

    def __init__(self, engine: EngineProvider, registry: ModelRegistry, trainer: ModelTrainer,
                 audit: AuditLog, feedback: FeedbackRepository):
        self._engine, self._registry, self._trainer = engine, registry, trainer
        self._audit, self._feedback = audit, feedback
        self._train_lock = threading.Lock()

    def reports(self, status: str | None = "pending") -> list[dict]:
        return self._feedback.list(status)

    def review(self, feedback_id: int, status: str, label: str | None = None) -> None:
        if not self._feedback.review(feedback_id, status, LABELS[label] if label else None):
            raise NotFound("feedback not found")

    def retrain(self) -> dict:
        if not self._train_lock.acquire(blocking=False):
            raise Conflict("A training run is already in progress")
        try:
            accepted = [LabeledText(f["text"], f["label"]) for f in self._feedback.list("accepted", 100_000)]
            version, metrics = self._trainer.train_new_version(accepted)
        finally:
            self._train_lock.release()
        active = self._engine.current.version
        return {"version": version, "metrics": metrics, "active_version": active,
                "active_metrics": self._registry.metrics(active) if active else {}}

    def models(self) -> dict:
        return {"active": self._engine.current.version,
                "versions": [{"version": v, "metrics": self._registry.metrics(v)}
                             for v in reversed(self._registry.versions())]}

    def activate(self, version: str) -> None:
        self._engine.activate(version)

    def stats(self) -> dict:
        return {"last_24h": self._audit.stats(86_400), "feedback_pending": self._feedback.pending_count()}
