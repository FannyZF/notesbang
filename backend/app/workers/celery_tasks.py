"""Celery tasks for the content-scoring product.

The worker is started with ``-A app.workers.celery_app:celery_app`` and
``celery_app`` includes this module, so every task below must be registered
here under the exact name ``runner.run_job`` sends (``jobs.<fn name>``).
"""
from __future__ import annotations

from app.workers.celery_app import celery_app


@celery_app.task(name="jobs.retention_cleanup")
def retention_cleanup() -> dict:
    from app.db.base import SessionLocal
    from app.services.cleanup import cleanup_expired

    db = SessionLocal()
    try:
        return cleanup_expired(db)
    finally:
        db.close()


@celery_app.task(name="jobs.run_analysis_task")
def run_analysis_task(job_id: int) -> None:
    from app.workers.jobs import run_analysis_task as analysis_body
    from app.workers.runner import execute_job

    execute_job(job_id, analysis_body)
