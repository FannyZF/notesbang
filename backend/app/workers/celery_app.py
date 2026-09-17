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
    # Imported when the worker/beat starts so task names are registered.
    include=["app.workers.celery_tasks"],
)
celery_app.conf.update(
    task_ignore_result=True,
    task_always_eager=_eager(),
    task_eager_propagates=True,
    broker_connection_retry_on_startup=True,
    task_default_queue="jobs",
)
celery_app.conf.beat_schedule = {
    "retention-cleanup-daily": {
        "task": "jobs.retention_cleanup",
        "schedule": 24 * 60 * 60,
    }
}
