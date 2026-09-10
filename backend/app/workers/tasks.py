"""Background job bodies for generation tasks (PRD §15).

Each function receives (db, job). Charging/trial-budget settlement happens
inside the task so a successful job is what triggers a charge (idempotent via
the ledger's unique job_id).
"""
from __future__ import annotations

from typing import Callable

from sqlalchemy.orm import Session

from app.models import Job, Page, Project, User
from app.services.billing import (
    ERROR_DUP_JOB,
    consume_generation_budget,
    is_paid,
    record_charge,
)


def _settle(db: Session, user: User, job: Job, pages: int, kind: str) -> None:
    if is_paid(user):
        try:
            record_charge(db, user, job.id, pages)
        except ValueError as exc:
            # A charge for this job already exists (e.g. retried worker after a
            # crash between charge and success). Idempotent: treat as done.
            if str(exc) != ERROR_DUP_JOB:
                raise
    else:
        consume_generation_budget(db, user, kind)


def _progress_of(job: Job, db: Session) -> Callable[[int, str], None]:
    def report(pct: int, phase: str) -> None:
        job.progress = int(pct)
        job.phase = phase
        db.commit()

    return report


def generate_whole_task(db: Session, job: Job) -> None:
    from app.pipeline.generator import generate

    project = db.get(Project, job.project_id)
    if project is None:
        raise RuntimeError("project not found")
    user = db.get(User, project.user_id)
    stats = generate(db, user, project, on_progress=_progress_of(job, db))
    page_count = (
        db.query(Page).filter(Page.project_id == project.id).count()
    )
    _settle(db, user, job, page_count, "whole")

    try:
        from app.core.metrics import GENERATED_PAGES, GENERATIONS, LLM_COST

        GENERATIONS.labels("success").inc()
        GENERATED_PAGES.inc(page_count)
        LLM_COST.inc(float(stats.get("cost", 0.0)))
    except Exception:  # noqa: BLE001
        pass

    from app.core.config import get_settings

    if get_settings().notify_on_complete:
        try:
            from app.services.mail import send_generation_ready

            send_generation_ready(get_settings(), user.email, project.title)
        except Exception:  # noqa: BLE001 - notification is best-effort
            pass


def generate_page_task(db: Session, job: Job) -> None:
    from app.pipeline.generator import generate

    project = db.get(Project, job.project_id)
    if project is None or job.target_id is None:
        raise RuntimeError("project or target page missing")
    user = db.get(User, project.user_id)
    page = (
        db.query(Page)
        .filter(Page.id == job.target_id, Page.project_id == project.id)
        .first()
    )
    if page is None:
        raise RuntimeError("page not found")
    generate(
        db,
        user,
        project,
        page_ids=[page.id],
        on_progress=_progress_of(job, db),
    )
    _settle(db, user, job, 1, "page")
