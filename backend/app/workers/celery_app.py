"""Celery application (broker = Redis; eager mode for tests)."""
from __future__ import annotations

import os

from celery import Celery

from app.core.config import get_settings


def _eager() -> bool:
    return os.getenv("CELERY_EAGER", "false").lower() in ("1", "true", "yes")


settings = get_settings()
celery_app = Celery(
    "notesbang",
    broker=settings.redis_url or "memory://",
    backend=None,
)
celery_app.conf.update(
    task_ignore_result=True,
    task_always_eager=_eager(),
    task_eager_propagates=True,
    broker_connection_retry_on_startup=True,
    task_default_queue="jobs",
)
