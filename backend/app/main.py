"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    routes_admin,
    routes_auth,
    routes_billing,
    routes_documents,
    routes_jobs,
    routes_track,
)
from app.core.config import get_settings
from app.core.metrics import HTTP_LATENCY, HTTP_REQUESTS, render_metrics
from app.core.observability import (
    init_sentry,
    new_request_id,
    request_id_ctx,
    setup_logging,
)
from app.db.base import init_db

setup_logging()
init_sentry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.getenv("ADMIN_TOKEN", "").strip():
        logging.getLogger("app").warning(
            "ADMIN_TOKEN is empty: /api/admin/* returns 503 and the /admin "
            "console cannot be used. Set it in .env and recreate the container."
        )
    init_db()
    yield


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

# Phase 0: permissive CORS for local Next.js dev; tighten before launch.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    rid = new_request_id()
    request_id_ctx.set(rid)
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - started
    path = request.url.path
    if path != "/metrics":
        HTTP_REQUESTS.labels(request.method, path, str(response.status_code)).inc()
        HTTP_LATENCY.labels(request.method, path).observe(elapsed)
    response.headers["X-Request-ID"] = rid
    return response


API_PREFIX = "/api"
app.include_router(routes_auth.router, prefix=API_PREFIX)
app.include_router(routes_billing.router, prefix=API_PREFIX)
app.include_router(routes_admin.router, prefix=API_PREFIX)
app.include_router(routes_documents.router, prefix=API_PREFIX)
app.include_router(routes_jobs.router, prefix=API_PREFIX)
app.include_router(routes_track.router, prefix=API_PREFIX)


@app.get("/healthz", tags=["system"])
def healthz() -> dict:
    return {"status": "ok", "environment": settings.environment}


@app.get("/metrics", tags=["system"])
def metrics() -> Response:
    data, content_type = render_metrics()
    return Response(content=data, media_type=content_type)
