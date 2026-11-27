"""FastAPI application.

Run locally (from the ``api`` folder)::

    uvicorn app.main:app --reload --port 8000

Then open http://localhost:8000/docs
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .analysis import router as analysis_router
from .cache import PhotoCache
from .config import Settings, get_settings
from .images import ImageError
from .models import ModelRegistry, load_registry

log = logging.getLogger("gopalan.api")


def create_app(settings: Settings | None = None, registry: ModelRegistry | None = None) -> FastAPI:
    """Build the app. Tests pass a ``registry`` with stand-in models."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if registry is not None:
            app.state.registry = registry
        elif settings.load_models:
            t0 = time.time()
            app.state.registry = load_registry(
                settings.detection_threshold, settings.breed_model_path, settings.breed_labels_path
            )
            log.info("Models loaded in %.1fs", time.time() - t0)
        else:
            app.state.registry = ModelRegistry(errors={"detector": "Model loading disabled", "breed": "Model loading disabled"})
        yield

    app = FastAPI(
        title="Gopalan AI API",
        version=__version__,
        description="Cattle and buffalo analysis: body points, measurements, body condition score (beta) and breed.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.photo_cache = PhotoCache(
        settings.cache_ttl_minutes * 60, settings.cache_max_entries, settings.cache_max_side
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_origin_regex=settings.allowed_origin_regex or None,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(ImageError)
    async def image_error(_: Request, exc: ImageError):
        return JSONResponse(status_code=exc.status, content={"error": "invalid_image", "message": str(exc)})

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException):
        # Same shape as other errors: {"error": ..., "message": ...}
        content = exc.detail if isinstance(exc.detail, dict) else {"error": "http_error", "message": str(exc.detail)}
        return JSONResponse(status_code=exc.status_code, content=content, headers=getattr(exc, "headers", None))

    app.include_router(analysis_router)

    @app.get("/health", tags=["system"])
    async def health(request: Request):
        reg: ModelRegistry = request.app.state.registry
        status = "ok" if reg.ready and reg.breed is not None else "degraded" if reg.ready else "unavailable"
        return {"status": status, "version": __version__, "models": reg.health()}

    return app


app = create_app()
