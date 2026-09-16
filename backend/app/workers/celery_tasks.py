"""Celery tasks for the content-scoring product."""
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
