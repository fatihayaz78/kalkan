"""Kalkan HTTP service.

    uvicorn kalkan.service.app:app --host 0.0.0.0 --port 8000

Public:  POST /v1/check, /v1/check/batch, /v1/check/messages, /v1/feedback
Admin:   /v1/admin/*  (feedback review, retrain, model versions, stats)
Ops:     GET /health, /ready, /metrics      UI: GET / (demo), GET /admin
"""
from __future__ import annotations

import threading
import uuid
from collections import Counter
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse

from .. import __version__
from ..augment import ALL_TRANSFORMS, apply
from ..cascade import Kalkan
from ..registry import ModelRegistry
from ..training import train_new_version
from .auth import client_name, require_admin
from .schemas import (BatchRequest, BatchResult, CheckRequest, CheckResult, FeedbackRequest, FeedbackReview,
                      MessageResult, MessagesRequest, MessagesResult)
from .settings import Settings
from .storage import Store

UI = Path(__file__).parent / "ui"
SEVERITY = {"allow": 0, "flag": 1, "block": 2}
LABELS = {"injection": 1, "benign": 0}


def create_app(settings: Settings | None = None) -> FastAPI:
    s = settings or Settings()
    app = FastAPI(title="Kalkan", version=__version__,
                  description="Turkish prompt-injection detection service. Call before every LLM request.")
    app.state.settings = s
    app.state.registry = ModelRegistry(s.models_dir)
    app.state.engine = Kalkan.from_registry(s.models_dir)
    app.state.store = Store(s.db_path)
    app.state.counts = Counter()
    app.state.train_lock = threading.Lock()

    def run_check(request: Request, client: str, text: str, source: str, trace: bool) -> CheckResult:
        if len(text) > s.max_chars:
            raise HTTPException(413, f"text exceeds {s.max_chars} characters; split long documents")
        v = request.app.state.engine.check(text, s.policy_for(client)).to_dict()
        rid = uuid.uuid4().hex
        request.app.state.store.log(rid, client, source, v, text, s.log_text)
        request.app.state.counts[(client, v["decision"])] += 1
        return CheckResult(request_id=rid, decision=v["decision"], score=v["score"], stage=v["stage"],
                           matched_rule=v["matched_rule"], model_version=v["model_version"],
                           latency_ms=v["latency_ms"], trace=v["trace"] if trace else None,
                           normalized=v["normalized"] if trace else None)

    # ------------------------------------------------------------- public API
    @app.post("/v1/check", response_model=CheckResult, response_model_exclude_none=True, tags=["detect"])
    def check(req: CheckRequest, request: Request, client: str = Depends(client_name)):
        """Check one untrusted text. Block the LLM call when decision is `block`."""
        return run_check(request, client, req.text, req.source, req.include_trace)

    @app.post("/v1/check/batch", response_model=BatchResult, response_model_exclude_none=True, tags=["detect"])
    def check_batch(req: BatchRequest, request: Request, client: str = Depends(client_name)):
        """Check several texts at once, e.g. all retrieved chunks of a RAG query."""
        if len(req.items) > s.max_batch:
            raise HTTPException(413, f"max {s.max_batch} items per batch")
        return BatchResult(results=[run_check(request, client, i.text, i.source, i.include_trace)
                                    for i in req.items])

    @app.post("/v1/check/messages", response_model=MessagesResult, response_model_exclude_none=True,
              tags=["detect"])
    def check_messages(req: MessagesRequest, request: Request, client: str = Depends(client_name)):
        """Check a chat transcript in OpenAI-style `messages` format.

        Only untrusted roles (user, tool, document) are checked; system and assistant are skipped.
        """
        msgs = list(enumerate(req.messages))
        if req.scope == "latest":
            last_assistant = max((i for i, m in msgs if m.role == "assistant"), default=-1)
            msgs = [(i, m) for i, m in msgs if i > last_assistant]
        results = []
        for i, m in msgs:
            if m.role in ("user", "tool", "document"):
                src = "user" if m.role == "user" else m.role
                r = run_check(request, client, m.content, src, False)
                results.append(MessageResult(**r.model_dump(), index=i, role=m.role))
        worst = max((r.decision for r in results), key=SEVERITY.get, default="allow")
        return MessagesResult(decision=worst, results=results)

    @app.post("/v1/feedback", status_code=201, tags=["feedback"])
    def feedback(req: FeedbackRequest, request: Request, client: str = Depends(client_name)):
        """Report a wrong decision. Goes to the admin review queue; used in the next retrain once accepted."""
        text = req.text or (request.app.state.store.audit_text(req.request_id) if req.request_id else None)
        if not text:
            raise HTTPException(422, "Send `text`, or a `request_id` whose text was logged.")
        fid = request.app.state.store.add_feedback(client, req.request_id, text, LABELS[req.label], req.note)
        return {"id": fid, "status": "pending"}

    @app.post("/v1/transform", tags=["demo"])
    def transform(body: dict, client: str = Depends(client_name)):
        """Apply evasion transforms (used by the demo UI's 'disguise' buttons)."""
        names = body.get("transforms", [])
        unknown = [t for t in names if t not in ALL_TRANSFORMS]
        if unknown or not isinstance(body.get("text"), str):
            raise HTTPException(422, f"Need text and transforms from {sorted(ALL_TRANSFORMS)}")
        return {"text": apply(body["text"][:10_000], names, body.get("seed"))}

    # ------------------------------------------------------------- admin API
    @app.get("/v1/admin/feedback", tags=["admin"])
    def list_feedback(request: Request, status: str | None = "pending", _: str = Depends(require_admin)):
        return request.app.state.store.list_feedback(status or None)

    @app.post("/v1/admin/feedback/{fid}", tags=["admin"])
    def review_feedback(fid: int, req: FeedbackReview, request: Request, _: str = Depends(require_admin)):
        label = LABELS[req.label] if req.label else None
        if not request.app.state.store.review_feedback(fid, req.status, label):
            raise HTTPException(404, "feedback not found")
        return {"id": fid, "status": req.status}

    @app.post("/v1/admin/retrain", tags=["admin"])
    def retrain(request: Request, _: str = Depends(require_admin)):
        """Train a new model version on the base data + accepted feedback. Does not activate it."""
        if not request.app.state.train_lock.acquire(blocking=False):
            raise HTTPException(409, "A training run is already in progress")
        try:
            extra = [{"text": f["text"], "label": f["label"]}
                     for f in request.app.state.store.list_feedback("accepted", limit=100_000)]
            version, metrics = train_new_version(request.app.state.registry, s.data_dir, extra)
        except FileNotFoundError as e:
            raise HTTPException(409, str(e))
        finally:
            request.app.state.train_lock.release()
        active = request.app.state.engine.version
        return {"version": version, "metrics": metrics,
                "active_version": active, "active_metrics": request.app.state.registry.metrics(active) if active else {}}

    @app.get("/v1/admin/models", tags=["admin"])
    def models(request: Request, _: str = Depends(require_admin)):
        reg = request.app.state.registry
        return {"active": request.app.state.engine.version,
                "versions": [{"version": v, "metrics": reg.metrics(v)} for v in reversed(reg.versions())]}

    @app.post("/v1/admin/models/{version}/activate", tags=["admin"])
    def activate(version: str, request: Request, _: str = Depends(require_admin)):
        reg = request.app.state.registry
        try:
            reg.activate(version)
        except (KeyError, ValueError):
            raise HTTPException(404, f"unknown version {version}")
        request.app.state.engine = Kalkan(reg.path(version), version)  # atomic swap
        return {"active": version}

    @app.get("/v1/admin/stats", tags=["admin"])
    def stats(request: Request, _: str = Depends(require_admin)):
        return request.app.state.store.stats()

    # ------------------------------------------------------------- ops + UI
    @app.get("/health", tags=["ops"])
    def health(request: Request):
        e = request.app.state.engine
        return {"status": "ok", "version": __version__, "model_version": e.version,
                "classical_loaded": e.classical is not None, "transformer_loaded": e.transformer is not None,
                "auth": "enabled" if s.auth_enabled else "disabled (dev mode)"}

    @app.get("/ready", tags=["ops"])
    def ready(request: Request):
        if request.app.state.engine.classical is None:
            raise HTTPException(503, "no model loaded")
        return {"ready": True}

    @app.get("/metrics", response_class=PlainTextResponse, tags=["ops"])
    def metrics(request: Request):
        lines = ["# TYPE kalkan_checks_total counter"]
        for (client, decision), n in sorted(request.app.state.counts.items()):
            lines.append(f'kalkan_checks_total{{client="{client}",decision="{decision}"}} {n}')
        return "\n".join(lines) + "\n"

    @app.get("/", include_in_schema=False)
    def demo_ui():
        return FileResponse(UI / "index.html")

    @app.get("/admin", include_in_schema=False)
    def admin_ui():
        return FileResponse(UI / "admin.html")

    return app


app = create_app()
