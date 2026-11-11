"""Request/response models: the public API contract (also published at /docs and /openapi.json)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Source = Literal["user", "document", "tool"]
Decision = Literal["allow", "flag", "block"]


class CheckRequest(BaseModel):
    text: str = Field(..., description="Untrusted text to check")
    source: Source = Field("user", description="user = typed by the end user; document/tool = retrieved or tool output")
    conversation_id: str | None = Field(None, max_length=200, description="Opaque id from the caller, stored in logs only")
    include_trace: bool = False


class CheckResult(BaseModel):
    request_id: str
    decision: Decision
    score: float = Field(..., description="0-1 injection likelihood; 1.0 for rule hits")
    stage: str
    matched_rule: str | None
    model_version: str | None
    latency_ms: float
    trace: list[dict] | None = None
    normalized: str | None = None


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
    decision: Decision = Field(..., description="Most severe decision across checked messages")
    results: list[MessageResult]


class FeedbackRequest(BaseModel):
    request_id: str | None = Field(None, description="From a previous check; text is looked up if it was logged")
    text: str | None = None
    label: Literal["injection", "benign"]
    note: str | None = Field(None, max_length=1000)


class FeedbackReview(BaseModel):
    status: Literal["accepted", "rejected"]
    label: Literal["injection", "benign"] | None = None
