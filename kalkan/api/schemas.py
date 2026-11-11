"""Request/response models: the public API contract (published at /docs and /openapi.json)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..application.services import CheckOutcome

SourceName = Literal["user", "document", "tool"]
DecisionName = Literal["allow", "flag", "block"]


class CheckRequest(BaseModel):
    text: str = Field(..., description="Untrusted text to check")
    source: SourceName = Field("user", description="user = typed by the end user; document/tool = retrieved or tool output")
    conversation_id: str | None = Field(None, max_length=200, description="Opaque caller id; not used for detection")
    include_trace: bool = False


class CheckResult(BaseModel):
    request_id: str
    decision: DecisionName
    score: float = Field(..., description="0-1 injection likelihood; 1.0 for rule hits")
    stage: str
    matched_rule: str | None
    model_version: str | None
    latency_ms: float
    trace: list[dict] | None = None
    normalized: str | None = None

    @classmethod
    def of(cls, o: CheckOutcome, include_trace: bool = False) -> "CheckResult":
        v = o.verdict
        return cls(request_id=o.request_id, decision=v.decision.value, score=v.score, stage=v.stage,
                   matched_rule=v.matched_rule, model_version=v.model_version, latency_ms=v.latency_ms,
                   trace=list(v.trace) if include_trace else None,
                   normalized=v.normalized if include_trace else None)


class BatchRequest(BaseModel):
    items: list[CheckRequest]


class BatchResult(BaseModel):
    results: list[CheckResult]


class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool", "document"]
    content: str


class MessagesRequest(BaseModel):
    messages: list[Message]
    conversation_id: str | None = None
    scope: Literal["latest", "all"] = Field(
        "latest", description="latest = messages after the last assistant turn; all = whole history")


class MessageResult(CheckResult):
    index: int
    role: str


class MessagesResult(BaseModel):
    decision: DecisionName = Field(..., description="Most severe decision across checked messages")
    results: list[MessageResult]


class FeedbackRequest(BaseModel):
    request_id: str | None = Field(None, description="From a previous check; its text is used if it was logged")
    text: str | None = None
    label: Literal["injection", "benign"]
    note: str | None = Field(None, max_length=1000)


class FeedbackReview(BaseModel):
    status: Literal["accepted", "rejected"]
    label: Literal["injection", "benign"] | None = None


class TransformRequest(BaseModel):
    text: str = Field(..., max_length=10_000)
    transforms: list[str]
    seed: int | None = None
