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


def _is_celery() -> bool:
    return os.getenv("TASK_BACKEND", "thread") == "celery"


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
    """Dispatch a job: Celery (Redis) when configured, else local thread/inline."""
    if _is_celery():
        from app.workers import celery_tasks  # noqa: F401  (register task names)
        from app.workers.celery_app import celery_app

        name = f"jobs.{task_fn.__name__}"
        if name not in celery_app.tasks:
            # Fail loudly instead of leaving the job stuck in "queued".
            raise RuntimeError(
                f"Celery task {name!r} is not registered; add it to "
                "app/workers/celery_tasks.py"
            )
        eager = os.getenv("CELERY_EAGER", "false").lower() in ("1", "true", "yes")
        if eager:
            # send_task ignores task_always_eager; invoke the registered task.
            celery_app.tasks[name](job_id)
        else:
            celery_app.send_task(name, args=[job_id])
        return
    if _is_async():
        _pool().submit(execute_job, job_id, task_fn)
    else:
        execute_job(job_id, task_fn)


def execute_job(job_id: int, task_fn: Callable[[SessionLocal, Job], None]) -> None:
    """Run a job body once, persisting running/succeeded/failed state.

    Shared by the thread executor and the Celery task so both backends behave
    identically.
    """
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
