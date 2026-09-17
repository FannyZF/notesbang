"""Background job bodies for the content-scoring product."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models import Document, Job


def run_analysis_task(db: Session, job: Job) -> None:
    from app.content import scoring
    from app.content.persist import save_analysis
    from app.llm.gateway import get_provider

    if job.document_id is None:
        raise RuntimeError("job has no document")
    doc = db.get(Document, job.document_id)
    if doc is None:
        raise RuntimeError("document not found")
    params = json.loads(job.params_json or "{}")
    focus = params.get("focus") or None

    def on_progress(pct: int, phase: str) -> None:
        job.progress = int(pct)
        job.phase = phase
        db.commit()

    result = scoring.analyze(
        get_provider(),
        title=doc.title,
        content=doc.content,
        platform=doc.platform,
        lang=doc.language if doc.language in ("zh", "en") else "en",
        focus=focus,
        on_progress=on_progress,
    )
    save_analysis(db, doc, result)
    job.progress = 100
    job.phase = "Done"
