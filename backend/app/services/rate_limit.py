"""In-process sliding-window rate limiter.

Phase-level guard for registration / login / trial abuse. The store lives in
process memory: fine for a single instance, and the interface is a drop-in
point for a Redis-backed limiter when we scale horizontally. Controlled by
``RATE_LIMIT_ENABLED`` (disabled in the test harness, see conftest).
"""
from __future__ import annotations

import os
import threading
import time

from fastapi import HTTPException, Request, status

_store: dict[str, list[float]] = {}
_lock = threading.Lock()


def enabled() -> bool:
    return os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("1", "true", "yes")


def client_ip(request: Request) -> str:
    from app.core.config import get_settings

    if get_settings().trust_proxy:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def reset() -> None:
    """Clear state (used by tests)."""
    global _store
    with _lock:
        _store.clear()


def enforce(scope: str, key: str, limit: int, window_seconds: int) -> None:
    if not enabled() or limit <= 0:
        return
    now = time.monotonic()
    store_key = f"{scope}:{key}"
    with _lock:
        timestamps = _store.get(store_key, [])
        timestamps = [t for t in timestamps if now - t < window_seconds]
        if len(timestamps) >= limit:
            retry = window_seconds - int(now - timestamps[0])
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests, please slow down and try again later.",
                headers={"X-Error-Code": "RATE_LIMITED", "Retry-After": str(max(1, retry))},
            )
        timestamps.append(now)
        _store[store_key] = timestamps
