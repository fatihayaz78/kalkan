"""Detection endpoints for consuming applications."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from ...detection.evasion import ALL_TRANSFORMS, apply
from ...domain.models import Source
from ..auth import client_name
from ..schemas import (BatchRequest, BatchResult, CheckRequest, CheckResult, FeedbackRequest, MessageResult,
                       MessagesRequest, MessagesResult, TransformRequest)

router = APIRouter(prefix="/v1")


def _c(request: Request):
    return request.app.state.container


def _count(request: Request, client: str, decision: str) -> None:
    _c(request).counts[(client, decision)] += 1


@router.post("/check", response_model=CheckResult, response_model_exclude_none=True, tags=["detect"])
def check(req: CheckRequest, request: Request, client: str = Depends(client_name)):
    """Check one untrusted text. Do not call the LLM when decision is `block`."""
    o = _c(request).guard.check(client, req.text, Source(req.source))
    _count(request, client, o.verdict.decision.value)
    return CheckResult.of(o, req.include_trace)


@router.post("/check/batch", response_model=BatchResult, response_model_exclude_none=True, tags=["detect"])
def check_batch(req: BatchRequest, request: Request, client: str = Depends(client_name)):
    """Check several texts at once, e.g. all retrieved chunks of a RAG query."""
    outs = _c(request).guard.check_many(client, [(i.text, Source(i.source)) for i in req.items])
    for o in outs:
        _count(request, client, o.verdict.decision.value)
    return BatchResult(results=[CheckResult.of(o, i.include_trace) for o, i in zip(outs, req.items)])


@router.post("/check/messages", response_model=MessagesResult, response_model_exclude_none=True, tags=["detect"])
def check_messages(req: MessagesRequest, request: Request, client: str = Depends(client_name)):
    """Check a chat transcript in OpenAI-style `messages` format. System and assistant turns are skipped."""
    worst, results = _c(request).guard.check_messages(
        client, [(m.role, m.content) for m in req.messages], latest_only=req.scope == "latest")
    for r in results:
        _count(request, client, r.outcome.verdict.decision.value)
    return MessagesResult(decision=worst.value, results=[
        MessageResult(**CheckResult.of(r.outcome).model_dump(), index=r.index, role=r.role) for r in results])


@router.post("/feedback", status_code=201, tags=["feedback"])
def feedback(req: FeedbackRequest, request: Request, client: str = Depends(client_name)):
    """Report a wrong decision. Goes to the admin review queue."""
    fid = _c(request).guard.report(client, req.label, req.request_id, req.text, req.note)
    return {"id": fid, "status": "pending"}


@router.post("/transform", tags=["demo"])
def transform(req: TransformRequest, client: str = Depends(client_name)):
    """Apply evasion transforms (used by the demo UI's disguise buttons)."""
    unknown = [t for t in req.transforms if t not in ALL_TRANSFORMS]
    if unknown:
        raise HTTPException(422, f"Unknown transforms {unknown}; available: {sorted(ALL_TRANSFORMS)}")
    return {"text": apply(req.text, req.transforms, req.seed)}
