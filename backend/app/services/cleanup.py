"""Retention / housekeeping for the content-scoring product.

Purges documents older than the retention window (and their derived data) to
honour data-retention promises (PRD §14.7.9).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Analysis, CorpusFeature, DimensionScore, Document, Feedback, Rewrite


def cleanup_expired(db: Session, ttl_days: int | None = None) -> dict:
    days = ttl_days if ttl_days is not None else int(get_settings().retention_days)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    purged = 0
    for doc in db.query(Document).all():
        created = doc.created_at
        if created is not None and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created is None or created >= cutoff:
            continue
        analysis_ids = [
            row[0]
            for row in db.query(Analysis.id).filter(Analysis.document_id == doc.id).all()
        ]
        if analysis_ids:
            db.query(DimensionScore).filter(
                DimensionScore.analysis_id.in_(analysis_ids)
            ).delete(synchronize_session=False)
        db.query(Analysis).filter(Analysis.document_id == doc.id).delete(
            synchronize_session=False
        )
        db.query(Rewrite).filter(Rewrite.document_id == doc.id).delete(
            synchronize_session=False
        )
        db.query(Feedback).filter(Feedback.document_id == doc.id).delete(
            synchronize_session=False
        )
        db.query(CorpusFeature).filter(CorpusFeature.document_id == doc.id).delete(
            synchronize_session=False
        )
        db.delete(doc)
        purged += 1
    db.commit()
    return {"documents": purged, "ttl_days": days}
