"""Retention / housekeeping: purge stored slide images for old projects.

Keeps storage bounded and honours data-retention promises (PRD §14.7.9).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Job, Page, Project
from app.services.storage import get_storage


def cleanup_expired(db: Session, ttl_days: int | None = None) -> dict:
    days = ttl_days if ttl_days is not None else int(get_settings().retention_days)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    storage = get_storage()

    old_projects = db.query(Project).all()
    purged_images = 0
    purged_projects = 0
    for project in old_projects:
        created = project.created_at
        if created is not None and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created is None or created >= cutoff:
            continue
        running = (
            db.query(Job)
            .filter(
                Job.project_id == project.id,
                Job.status.in_(["queued", "running"]),
            )
            .first()
        )
        if running is not None:
            continue
        pages = db.query(Page).filter(Page.project_id == project.id).all()
        for page in pages:
            if page.image_key:
                storage.delete(page.image_key)
                page.image_key = None
                purged_images += 1
        purged_projects += 1
    db.commit()
    return {"projects": purged_projects, "images": purged_images, "ttl_days": days}
