"""Celery task wrappers around the plain job functions in ``tasks.py``."""
from __future__ import annotations

from app.workers import tasks as job_tasks
from app.workers.celery_app import celery_app
from app.workers.runner import _work


@celery_app.task(name="jobs.generate_whole_task")
def generate_whole_task(job_id: int) -> None:
    _work(job_id, job_tasks.generate_whole_task)


@celery_app.task(name="jobs.generate_page_task")
def generate_page_task(job_id: int) -> None:
    _work(job_id, job_tasks.generate_page_task)


@celery_app.task(name="jobs.retention_cleanup")
def retention_cleanup() -> dict:
    from app.db.base import SessionLocal
    from app.services.cleanup import cleanup_expired

    db = SessionLocal()
    try:
        return cleanup_expired(db)
    finally:
        db.close()
