"""Kalkan HTTP service.

    uvicorn kalkan.api.app:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .. import __version__
from ..application.errors import Conflict, InvalidRequest, KalkanError, NotFound, PayloadTooLarge
from .container import Container
from .routes import admin, ops, public
from .settings import Settings

STATUS = {InvalidRequest: 422, PayloadTooLarge: 413, NotFound: 404, Conflict: 409}


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Kalkan", version=__version__,
                  description="Turkish prompt-injection detection service. Call before every LLM request.")
    app.state.container = Container.build(settings or Settings())

    @app.exception_handler(KalkanError)
    async def _errors(_: Request, exc: KalkanError):
        return JSONResponse({"detail": str(exc)}, status_code=STATUS.get(type(exc), 400))

    for r in (public.router, admin.router, ops.router):
        app.include_router(r)
    return app


app = create_app()
