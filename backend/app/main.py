"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    routes_admin,
    routes_auth,
    routes_billing,
    routes_projects,
    routes_speech,
    routes_styles,
)
from app.core.config import get_settings
from app.db.base import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
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

API_PREFIX = "/api"
app.include_router(routes_auth.router, prefix=API_PREFIX)
app.include_router(routes_projects.router, prefix=API_PREFIX)
app.include_router(routes_billing.router, prefix=API_PREFIX)
app.include_router(routes_speech.router, prefix=API_PREFIX)
app.include_router(routes_styles.router, prefix=API_PREFIX)
app.include_router(routes_admin.router, prefix=API_PREFIX)


@app.get("/healthz", tags=["system"])
def healthz() -> dict:
    return {"status": "ok", "environment": settings.environment}
