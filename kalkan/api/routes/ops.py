"""Health, readiness, metrics and the two UI pages."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse

from ... import __version__

UI = Path(__file__).resolve().parents[1] / "ui"
router = APIRouter()


@router.get("/health", tags=["ops"])
def health(request: Request):
    c = request.app.state.container
    p = c.engine.current
    return {"status": "ok", "version": __version__, "model_version": p.version, "stages": p.stage_names,
            "auth": "enabled" if c.auth.enabled else "disabled (dev mode)"}


@router.get("/ready", tags=["ops"])
def ready(request: Request):
    if "classical" not in request.app.state.container.engine.current.stage_names:
        raise HTTPException(503, "no model loaded")
    return {"ready": True}


@router.get("/metrics", response_class=PlainTextResponse, tags=["ops"])
def metrics(request: Request):
    lines = ["# TYPE kalkan_checks_total counter"]
    for (client, decision), n in sorted(request.app.state.container.counts.items()):
        lines.append(f'kalkan_checks_total{{client="{client}",decision="{decision}"}} {n}')
    return "\n".join(lines) + "\n"


@router.get("/", include_in_schema=False)
def demo_ui():
    return FileResponse(UI / "index.html")


@router.get("/admin", include_in_schema=False)
def admin_ui():
    return FileResponse(UI / "admin.html")
