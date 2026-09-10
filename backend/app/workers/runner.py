"""Job execution: inline (tests / local) or background thread pool (Phase 2).

PRD §15: tasks run asynchronously and the client polls job state. A Celery/Redis
deployment can replace the thread executor later without touching the tasks,
which are plain ``fn(db, job)`` callables.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from app.db.base import SessionLocal
from app.models import Job

_executor: ThreadPoolExecutor | None = None


def _is_async() -> bool:
    return os.getenv("EXEC_ASYNC", "false").lower() in ("1", "true", "yes")


def _pool() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        from app.core.config import get_settings

        _executor = ThreadPoolExecutor(
            max_workers=get_settings().async_max_workers,
            thread_name_prefix="job",
        )
    return _executor


def run_job(job_id: int, task_fn: Callable[[SessionLocal, Job], None]) -> None:
    """Enqueue (async) or execute immediately (inline) a job by id."""
    if _is_async():
        _pool().submit(_work, job_id, task_fn)
    else:
        _work(job_id, task_fn)


def _work(job_id: int, task_fn: Callable[[SessionLocal, Job], None]) -> None:
    db = SessionLocal()
    job: Job | None = None
    try:
        job = db.get(Job, job_id)
        if job is None or job.status != "queued":
            return
        job.status = "running"
        job.progress = 5
        db.commit()
        task_fn(db, job)
        db.refresh(job)
        job.status = "succeeded"
        job.progress = 100
        job.phase = "Finalizing"
        db.commit()
    except Exception as exc:  # noqa: BLE001 - persist failure for polling
        try:
            if job is not None:
                job.status = "failed"
                job.progress = 0
                job.error = str(exc)[:500]
                db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
    finally:
        db.close()
