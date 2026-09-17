"""Job status API (polling) for async analyses."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models import Document, Job, User

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
def get_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.document_id is not None:
        doc = db.get(Document, job.document_id)
        if doc is None or doc.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job not found")
    return {
        "id": job.id,
        "type": job.type,
        "document_id": job.document_id,
        "status": job.status,
        "phase": job.phase or "",
        "progress": job.progress,
        "error": job.error,
    }
