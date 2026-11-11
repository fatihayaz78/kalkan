"""Domain entities and value objects."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from typing import Any, Mapping


class Decision(str, Enum):
    ALLOW = "allow"
    FLAG = "flag"
    BLOCK = "block"

    @property
    def severity(self) -> int:
        return {"allow": 0, "flag": 1, "block": 2}[self.value]

    @classmethod
    def most_severe(cls, decisions) -> "Decision":
        return max(decisions, key=lambda d: d.severity, default=cls.ALLOW)


class Source(str, Enum):
    USER = "user"          # typed by the end user
    DOCUMENT = "document"  # retrieved content (RAG, web page, e-mail)
    TOOL = "tool"          # output of a tool / function call


@dataclass(frozen=True)
class Policy:
    """Thresholds that turn a score into a decision. Immutable; per-client overrides create a copy."""
    classical_allow_below: float = 0.15
    flag_at: float = 0.50
    block_at: float = 0.80

    def decide(self, score: float) -> Decision:
        if score >= self.block_at:
            return Decision.BLOCK
        if score >= self.flag_at:
            return Decision.FLAG
        return Decision.ALLOW

    def with_overrides(self, overrides: Mapping[str, float] | None) -> "Policy":
        known = {k: float(v) for k, v in (overrides or {}).items() if k in self.__dataclass_fields__}
        return replace(self, **known)


@dataclass(frozen=True)
class NormalizedText:
    original: str
    lower: str   # Turkish-lowercased and cleaned, keeps diacritics
    folded: str  # ASCII-folded, de-leeted, spacing collapsed


@dataclass(frozen=True)
class StageResult:
    """Outcome of one detection stage. decision=None means 'undecided, ask the next stage'."""
    stage: str
    decision: Decision | None = None
    score: float | None = None
    rule: str | None = None
    detail: Mapping[str, Any] = field(default_factory=dict)

    def as_trace(self) -> dict:
        t = {"stage": self.stage}
        if self.score is not None:
            t["score"] = round(self.score, 4)
        if self.rule:
            t["rule"] = self.rule
        if self.decision:
            t["decision"] = self.decision.value
        return {**t, **self.detail}


@dataclass(frozen=True)
class Verdict:
    decision: Decision
    score: float
    stage: str
    matched_rule: str | None
    latency_ms: float
    model_version: str | None
    trace: tuple[dict, ...] = ()
    normalized: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["decision"] = self.decision.value
        d["trace"] = list(self.trace)
        return d


@dataclass(frozen=True)
class AuditRecord:
    request_id: str
    client: str
    source: Source
    verdict: Verdict
    text: str


@dataclass(frozen=True)
class LabeledText:
    text: str
    label: int  # 1 = injection, 0 = benign
