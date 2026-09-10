"""Sliding-window rate limiter.

Uses Redis when ``REDIS_URL`` is configured (multi-instance safe) and falls
back to an in-process store for dev/tests. Controlled by ``RATE_LIMIT_ENABLED``.
"""
from __future__ import annotations

import os
import threading
import time

from fastapi import HTTPException, Request, status

_store: dict[str, list[float]] = {}
_lock = threading.Lock()
_redis_client = None


def enabled() -> bool:
    return os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("1", "true", "yes")


def _get_redis():
    global _redis_client
    url = os.getenv("REDIS_URL", "")
    if not url:
        return None
    if _redis_client is None:
        try:
            import redis

            _redis_client = redis.from_url(url, decode_responses=True)
        except Exception:  # noqa: BLE001 - fall back to memory
            _redis_client = False
    return _redis_client or None


def client_ip(request: Request) -> str:
    from app.core.config import get_settings

    if get_settings().trust_proxy:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def reset() -> None:
    """Clear in-process state (tests). Redis keys expire on their own."""
    global _store
    with _lock:
        _store.clear()


def _raise(retry: int) -> None:
    raise HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many requests, please slow down and try again later.",
        headers={"X-Error-Code": "RATE_LIMITED", "Retry-After": str(max(1, retry))},
    )


def enforce(scope: str, key: str, limit: int, window_seconds: int) -> None:
    if not enabled() or limit <= 0:
        return
    store_key = f"rl:{scope}:{key}"
    client = _get_redis()
    if client is not None:
        now = time.time()
        pipe = client.pipeline()
        pipe.zremrangebyscore(store_key, 0, now - window_seconds)
        pipe.zcard(store_key)
        results = pipe.execute()
        count = int(results[1])
        if count >= limit:
            _raise(window_seconds)
        pipe = client.pipeline()
        pipe.zadd(store_key, {f"{now}": now})
        pipe.expire(store_key, window_seconds + 1)
        pipe.execute()
        return

    now = time.monotonic()
    with _lock:
        timestamps = _store.get(store_key, [])
        timestamps = [t for t in timestamps if now - t < window_seconds]
        if len(timestamps) >= limit:
            _raise(window_seconds - int(now - timestamps[0]))
        timestamps.append(now)
        _store[store_key] = timestamps
