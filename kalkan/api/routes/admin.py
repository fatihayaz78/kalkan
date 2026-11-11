"""Operator endpoints: review reports, retrain, model versions, stats."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..auth import require_admin
from ..schemas import FeedbackReview

router = APIRouter(prefix="/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _admin(request: Request):
    return request.app.state.container.admin


@router.get("/feedback")
def list_feedback(request: Request, status: str | None = "pending"):
    return _admin(request).reports(status or None)


@router.post("/feedback/{feedback_id}")
def review_feedback(feedback_id: int, req: FeedbackReview, request: Request):
    _admin(request).review(feedback_id, req.status, req.label)
    return {"id": feedback_id, "status": req.status}


@router.post("/retrain")
def retrain(request: Request):
    """Train a new version on base data + accepted reports. Does not activate it."""
    return _admin(request).retrain()


@router.get("/models")
def models(request: Request):
    return _admin(request).models()


@router.post("/models/{version}/activate")
def activate(version: str, request: Request):
    _admin(request).activate(version)
    return {"active": version}


@router.get("/stats")
def stats(request: Request):
    return _admin(request).stats()
