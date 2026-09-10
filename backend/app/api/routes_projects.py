"""Project routes: upload + parse pipeline, preview, list."""
from __future__ import annotations

from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_verified
from app.core.config import Settings, get_settings
from app.core.counters import count_chars
from app.db.base import get_db
from app.models import Job, Page, Project, User
from app.parsers import pptx_parser
from app.schemas import (
    GenerateOut,
    GenerationSettingsIn,
    JobOut,
    PageOut,
    PageRevisionOut,
    PageSummary,
    PageUpdateIn,
    PlanOut,
    PlanPage,
    ProjectOut,
    RestoreIn,
    ReviewOut,
    StructureIn,
    StructureOut,
    StructureSectionOut,
    SummaryOut,
)
from app.services.billing import (
    ERROR_INSUFFICIENT,
    can_generate_unpaid,
    can_upload_pages,
    export_locked,
    is_paid,
    required_price_pages,
)
from app.services.rate_limit import enforce
from app.services.storage import get_storage

router = APIRouter(prefix="/projects", tags=["projects"])

_ALLOWED_EXTS = {".pptx"}


@router.post("", response_model=ProjectOut, status_code=201)
async def upload_project(
    file: UploadFile = File(...),
    request: Request = None,  # type: ignore[assignment]
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    settings: Settings = get_settings()
    enforce("upload_user", f"u{user.id}", settings.upload_user_per_hour, 3600)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only .pptx is supported in Phase 0",
            headers={"X-Error-Code": "UNSUPPORTED_FORMAT"},
        )

    source_key = f"{user.id}/{Path(file.filename or 'file.pptx').name}"
    storage = get_storage()
    storage.save_bytes(source_key, await file.read())

    try:
        with storage.materialize(source_key) as src:
            page_count = pptx_parser.count_pptx_pages(str(src))
    except Exception as exc:  # corrupt / malformed pptx
        storage.delete(source_key)
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to open PPTX; file may be corrupted",
            headers={"X-Error-Code": "PARSE_FAILED"},
        ) from exc

    allowed, reason = can_upload_pages(user, page_count)
    if not allowed:
        storage.delete(source_key)
        code = 402 if reason == "TRIAL_USED_NEED_FUNDS" else 403
        raise HTTPException(
            code,
            detail=reason,
            headers={"X-Error-Code": reason},
        )

    project = Project(
        user_id=user.id,
        title=file.filename or "Untitled",
        source_format="pptx",
        source_key=source_key,
        status="parsing",
    )
    db.add(project)
    db.flush()

    job = Job(project_id=project.id, type="parse", status="running")
    db.add(job)
    db.flush()

    try:
        with storage.materialize(source_key) as src:
            pages = pptx_parser.parse_pptx(str(src))
    except Exception as exc:
        project.status = "parse_failed"
        job.status = "failed"
        job.error = str(exc)[:500]
        db.commit()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="PPTX parsing failed",
            headers={"X-Error-Code": "PARSE_FAILED"},
        ) from exc

    created_pages: list[Page] = []
    for p in pages:
        page = Page(
            project_id=project.id,
            ord=p.ord,
            raw_text=p.text,
            status="parsed",
        )
        db.add(page)
        created_pages.append(page)
    db.flush()

    # Optional: render slide images (thumbnails + vision). Best-effort.
    if settings.render_slides:
        try:
            from app.rendering.slides import render_pages

            with storage.materialize(source_key) as src:
                images = render_pages(src)
            for page, png in zip(created_pages, images):
                key = f"{user.id}/{project.id}/pages/{page.ord}.png"
                storage.save_bytes(key, png)
                page.image_key = key
        except Exception:  # noqa: BLE001 - rendering must not break upload
            pass

    project.status = "parsed"
    job.status = "succeeded"
    job.progress = 100
    db.commit()

    # Re-select with pages eager for response.
    created = (
        db.query(Project)
        .filter(Project.id == project.id)
        .first()
    )
    settings  # reserved
    return ProjectOut.model_validate(created)


@router.get("", response_model=list[ProjectOut])
def list_projects(
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Project)
        .filter(Project.user_id == user.id)
        .order_by(Project.created_at.desc())
        .all()
    )
    _mark_running(db, rows)
    return [ProjectOut.model_validate(p) for p in rows]


@router.post("/{project_id}/export")
def export_project(
    project_id: int,
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
    fmt: str = Query(default="pptx"),
    strategy: str = Query(default="overwrite"),
):
    """Phase 2 real export: PPTX notes write-back or Word script.

    Gate (PRD §2.2): trial/unfunded users are locked out with 402.
    """
    if fmt not in ("pptx", "docx", "pdf"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="fmt must be pptx, docx or pdf",
            headers={"X-Error-Code": "BAD_FMT"},
        )
    if strategy not in ("overwrite", "merge"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="strategy must be overwrite or merge",
            headers={"X-Error-Code": "BAD_STRATEGY"},
        )
    project = _owned_project(db, project_id, user)
    if export_locked(user):
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            detail="Top up to unlock export",
            headers={"X-Error-Code": "EXPORT_LOCKED"},
        )
    pages = (
        db.query(Page)
        .filter(Page.project_id == project.id)
        .order_by(Page.ord)
        .all()
    )
    if not pages:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No pages",
            headers={"X-Error-Code": "NO_PAGES"},
        )
    if any(not p.note_text for p in pages):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Generate notes before exporting",
            headers={"X-Error-Code": "NOTES_MISSING"},
        )

    stem = Path(project.title or "notesbang").stem or "notesbang"
    if fmt == "pdf":
        from app.exporters.pdf_writer import write_pdf

        content = write_pdf(
            project.title or "Speaker Notes",
            [(f"Slide {p.ord}", p.note_text) for p in pages],
        )
        media_type = "application/pdf"
        filename = f"{stem}_notes.pdf"
    elif fmt == "docx":
        from app.exporters.docx_writer import write_docx

        content = write_docx(
            project.title or "Speaker Notes",
            [(f"Slide {p.ord}", p.note_text) for p in pages],
        )
        media_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        filename = f"{stem}_notes.docx"
    else:
        from app.exporters.pptx_writer import write_pptx_notes

        storage = get_storage()
        if not storage.exists(project.source_key):
            raise HTTPException(
                status.HTTP_410_GONE,
                detail="Original file missing",
                headers={"X-Error-Code": "SOURCE_MISSING"},
            )
        with storage.materialize(project.source_key) as src:
            content = write_pptx_notes(
                src, [(p.ord, p.note_text) for p in pages], strategy=strategy
            )
        media_type = (
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
        filename = f"{stem}_notes.pptx"

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{_url_quote(filename)}"
            )
        },
    )


def _url_quote(value: str) -> str:
    import urllib.parse

    return urllib.parse.quote(value)


@router.get("/{project_id}/summary", response_model=SummaryOut)
def project_summary(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.pipeline.generator import resolve_speed_cps

    project = _owned_project(db, project_id, user)
    pages = (
        db.query(Page)
        .filter(Page.project_id == project.id)
        .order_by(Page.ord)
        .all()
    )
    cps = resolve_speed_cps(user, project)
    per_page = [PageSummary(ord=p.ord, chars=count_chars(p.note_text)) for p in pages]
    total = sum(item.chars for item in per_page)
    est = total / max(cps * 60 * get_settings().pacing_factor, 0.0001)
    return SummaryOut(
        project_id=project.id,
        total_chars=total,
        speed_cps=cps,
        est_minutes=round(est, 1),
        target_minutes=project.target_minutes,
        pages=per_page,
    )


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    """Delete a project and all its data (PRD §14.4 account cleanup)."""
    from app.models import GenerationLog, Job, PageRevision, Section

    project = _owned_project(db, project_id, user)
    page_ids = [
        row[0] for row in db.query(Page.id).filter(Page.project_id == project.id).all()
    ]
    if page_ids:
        db.query(PageRevision).filter(PageRevision.page_id.in_(page_ids)).delete(
            synchronize_session=False
        )
    db.query(GenerationLog).filter(GenerationLog.project_id == project.id).delete(
        synchronize_session=False
    )
    db.query(Job).filter(Job.project_id == project.id).delete(synchronize_session=False)
    db.query(Section).filter(Section.project_id == project.id).delete(
        synchronize_session=False
    )
    db.query(Page).filter(Page.project_id == project.id).delete(synchronize_session=False)
    get_storage().delete(project.source_key)
    db.delete(project)
    db.commit()
    return {"ok": True, "deleted_project_id": project.id}


@router.delete("/{project_id}/pages/{page_id}")
def delete_page(
    project_id: int,
    page_id: int,
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    project = _owned_project(db, project_id, user)
    page = (
        db.query(Page)
        .filter(Page.id == page_id, Page.project_id == project.id)
        .first()
    )
    if page is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Page not found")
    db.delete(page)
    db.commit()
    remaining = _page_count(db, project.id)
    return {"ok": True, "remaining": remaining}


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = (
        db.query(Project)
        .filter(
            Project.id == project_id,
            Project.user_id == user.id,
        )
        .first()
    )
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Project not found")
    _mark_running(db, [project])
    return ProjectOut.model_validate(project)


def _mark_running(db: Session, projects: list[Project]) -> None:
    ids = [p.id for p in projects]
    if not ids:
        return
    rows = (
        db.query(Job.project_id)
        .filter(Job.project_id.in_(ids), Job.status.in_(["queued", "running"]))
        .distinct()
        .all()
    )
    running = {r[0] for r in rows}
    for p in projects:
        p.running = p.id in running


def _owned_project(db: Session, project_id: int, user: User) -> Project:
    project = (
        db.query(Project)
        .filter(
            Project.id == project_id,
            Project.user_id == user.id,
        )
        .first()
    )
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _page_count(db: Session, project_id: int) -> int:
    return (
        db.query(Page).filter(Page.project_id == project_id).count()
    )


def _apply_settings(project: Project, payload: GenerationSettingsIn) -> None:
    # exclude_unset keeps explicit nulls (e.g. clearing style_profile_id).
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)


@router.put("/{project_id}/settings", response_model=ProjectOut)
def update_settings(
    project_id: int,
    payload: GenerationSettingsIn,
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    from app.llm.renderer import available_styles

    if payload.style is not None and payload.style not in available_styles():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown style: {payload.style}",
            headers={"X-Error-Code": "UNKNOWN_STYLE"},
        )
    if payload.speed_source == "manual" and not payload.speed_cps:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="speed_cps is required for manual speed source",
            headers={"X-Error-Code": "SPEED_CPS_REQUIRED"},
        )
    if payload.note_mode is not None and payload.note_mode not in ("script", "cue"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="note_mode must be script or cue",
            headers={"X-Error-Code": "BAD_NOTE_MODE"},
        )
    if payload.quality_mode is not None and payload.quality_mode not in ("full", "fast"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="quality_mode must be full or fast",
            headers={"X-Error-Code": "BAD_QUALITY_MODE"},
        )
    if payload.style_profile_id is not None:
        from app.models import StyleProfile

        profile = (
            db.query(StyleProfile)
            .filter(
                StyleProfile.id == payload.style_profile_id,
                StyleProfile.user_id == user.id,
            )
            .first()
        )
        if profile is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="style_profile_id not found or not owned",
                headers={"X-Error-Code": "BAD_STYLE_PROFILE"},
            )
    project = _owned_project(db, project_id, user)
    _apply_settings(project, payload)
    db.commit()
    db.refresh(project)
    return ProjectOut.model_validate(project)


@router.post("/{project_id}/plan", response_model=PlanOut)
def plan_generation(
    project_id: int,
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    from app.length.allocator import allocate_targets
    from app.pipeline.generator import resolve_speed_cps

    project = _owned_project(db, project_id, user)
    pages = (
        db.query(Page)
        .filter(Page.project_id == project_id)
        .order_by(Page.ord)
        .all()
    )
    if not pages:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No pages",
            headers={"X-Error-Code": "NO_PAGES"},
        )
    settings = get_settings()
    cps = resolve_speed_cps(user, project)
    total_units = int(project.target_minutes * 60 * cps * settings.pacing_factor)
    targets = allocate_targets(
        [p.raw_text for p in pages], [p.weight or 1.0 for p in pages], total_units
    )
    return PlanOut(
        project_id=project.id,
        total_units=total_units,
        unit_name="字",
        target_minutes=project.target_minutes,
        speed_cps=cps,
        pages=[
            PlanPage(ord=p.ord, page_id=p.id, weight=p.weight, target_chars=t)
            for p, t in zip(pages, targets)
        ],
    )


def _guard_generation(user: User, pages: int) -> None:
    """Reject generation that the wallet/trial budget cannot cover."""
    if is_paid(user):
        need = pages * get_settings().price_per_page_points
        if (user.wallet and user.wallet.balance >= need) or need == 0:
            return
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient balance",
            headers={"X-Error-Code": ERROR_INSUFFICIENT},
        )
    ok, code = can_generate_unpaid(user, "whole")
    if not ok:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            detail="Trial budget used; top up to continue",
            headers={"X-Error-Code": code},
        )


def _assert_no_running(db: Session, project_id: int, job_type: str) -> None:
    running = (
        db.query(Job)
        .filter(
            Job.project_id == project_id,
            Job.type == job_type,
            Job.status.in_(["queued", "running"]),
        )
        .first()
    )
    if running is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="A generation is already running for this project",
            headers={"X-Error-Code": "JOB_ALREADY_RUNNING", "X-Job-Id": str(running.id)},
        )


@router.post("/{project_id}/generate", response_model=GenerateOut)
def generate_whole(
    project_id: int,
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    project = _owned_project(db, project_id, user)
    pages = _page_count(db, project.id)
    if pages == 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No pages")
    _guard_generation(user, pages)
    _assert_no_running(db, project.id, "generate_whole")

    job = Job(
        project_id=project.id,
        type="generate_whole",
        status="queued",
        charge_amount=required_price_pages(user, pages),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    from app.workers import tasks
    from app.workers.runner import _is_async, run_job

    run_job(job.id, tasks.generate_whole_task)
    db.refresh(job)

    if _is_async():
        return _queued_out(project, job)
    if job.status != "succeeded":
        _raise_job_failure(job)

    generated = (
        db.query(Page)
        .filter(Page.project_id == project.id, Page.status == "generated")
        .count()
    )
    total_units = sum(
        (p.target_chars or 0)
        for p in db.query(Page).filter(Page.project_id == project.id)
    )
    return GenerateOut(
        job_id=job.id,
        project_id=project.id,
        status="succeeded",
        updated_pages=generated,
        total_units=total_units,
        mode=project.note_mode,
        charged_points=job.charge_amount,
    )


def _guard_page_regen(user: User) -> None:
    if is_paid(user):
        return
    ok, code = can_generate_unpaid(user, "page")
    if not ok:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            detail="Trial page-regeneration budget used; top up to continue",
            headers={"X-Error-Code": code},
        )


@router.post("/{project_id}/pages/{page_id}/regenerate", response_model=GenerateOut)
def regenerate_page(
    project_id: int,
    page_id: int,
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    project = _owned_project(db, project_id, user)
    page = (
        db.query(Page)
        .filter(Page.id == page_id, Page.project_id == project.id)
        .first()
    )
    if page is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Page not found")
    _guard_page_regen(user)
    _assert_no_running(db, project.id, "generate_page")

    job = Job(
        project_id=project.id,
        type="generate_page",
        target_id=page.id,
        status="queued",
        charge_amount=required_price_pages(user, 1),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    from app.workers import tasks
    from app.workers.runner import _is_async, run_job

    run_job(job.id, tasks.generate_page_task)
    db.refresh(job)

    if _is_async():
        return _queued_out(project, job)
    if job.status != "succeeded":
        _raise_job_failure(job)

    return GenerateOut(
        job_id=job.id,
        project_id=project.id,
        status="succeeded",
        updated_pages=1,
        total_units=0,
        mode=project.note_mode,
        charged_points=job.charge_amount,
    )


@router.get("/{project_id}/jobs", response_model=list[JobOut])
def project_jobs(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _owned_project(db, project_id, user)
    rows = (
        db.query(Job)
        .filter(Job.project_id == project_id)
        .order_by(Job.id.desc())
        .limit(10)
        .all()
    )
    return [JobOut.model_validate(j) for j in rows]


def _queued_out(project: Project, job: Job) -> GenerateOut:
    return GenerateOut(
        job_id=job.id,
        project_id=project.id,
        status=job.status,
        updated_pages=0,
        total_units=0,
        mode=project.note_mode,
        charged_points=job.charge_amount,
    )


def _raise_job_failure(job: Job) -> None:
    err = job.error or "Job failed"
    code = "GENERATION_FAILED"
    http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
    if ERROR_INSUFFICIENT in err:
        code = ERROR_INSUFFICIENT
        http_status = status.HTTP_402_PAYMENT_REQUIRED
    raise HTTPException(
        http_status,
        detail=err,
        headers={"X-Error-Code": code},
    )


@router.get("/{project_id}/pages/{page_id}/image")
def get_page_image(
    project_id: int,
    page_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = _owned_project(db, project_id, user)
    page = (
        db.query(Page)
        .filter(Page.id == page_id, Page.project_id == project.id)
        .first()
    )
    if page is None or not page.image_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No slide image")
    data = get_storage().read_bytes(page.image_key)
    return Response(content=data, media_type="image/png")


@router.put("/{project_id}/pages/{page_id}", response_model=PageOut)
def update_page(
    project_id: int,
    page_id: int,
    payload: PageUpdateIn,
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    """Edit notes / weight / mode with optimistic concurrency (PRD §4.10).

    Before overwriting an existing note a PageRevision backup is written so a
    later regenerate can be undone by the user.
    """
    from app.models import PageRevision

    project = _owned_project(db, project_id, user)
    page = (
        db.query(Page)
        .filter(Page.id == page_id, Page.project_id == project.id)
        .first()
    )
    if page is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Page not found")

    if payload.expected_version is not None and payload.expected_version != page.version:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Page was modified elsewhere",
            headers={"X-Error-Code": "REVISION_CONFLICT", "X-Current-Version": str(page.version)},
        )

    if payload.weight is not None and payload.weight != page.weight:
        from math import ceil
        from sqlalchemy import func

        total_pages = (
            db.query(func.count(Page.id))
            .filter(Page.project_id == project.id)
            .scalar()
            or 1
        )
        limit = max(1, ceil(total_pages * 0.2))
        others = (
            db.query(Page)
            .filter(Page.project_id == project.id, Page.id != page.id)
            .all()
        )
        already_emph = sum(1 for p in others if (p.weight or 1.0) >= 1.5)
        now_emph = payload.weight >= 1.5
        was_emph = (page.weight or 1.0) >= 1.5
        if now_emph and not was_emph and already_emph + 1 > limit:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="At most 20% of slides can be emphasized",
                headers={"X-Error-Code": "EMPHASIS_LIMIT"},
            )

    changed = False
    if payload.note_text is not None and payload.note_text != page.note_text:
        db.add(
            PageRevision(
                page_id=page.id,
                note_text=page.note_text or "",
                actor="user",
            )
        )
        page.note_text = payload.note_text
        changed = True
    if payload.weight is not None and payload.weight != page.weight:
        page.weight = payload.weight
        changed = True
    if payload.note_mode is not None and payload.note_mode != page.note_mode:
        page.note_mode = payload.note_mode
        changed = True
    if changed:
        page.version += 1
    db.commit()
    db.refresh(page)
    return PageOut.model_validate(page)


@router.get("/{project_id}/pages/{page_id}/revisions", response_model=list[PageRevisionOut])
def list_page_revisions(
    project_id: int,
    page_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models import PageRevision

    project = _owned_project(db, project_id, user)
    page = (
        db.query(Page)
        .filter(Page.id == page_id, Page.project_id == project.id)
        .first()
    )
    if page is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Page not found")
    rows = (
        db.query(PageRevision)
        .filter(PageRevision.page_id == page.id)
        .order_by(PageRevision.id.desc())
        .limit(20)
        .all()
    )
    return [PageRevisionOut.model_validate(r) for r in rows]


@router.put("/{project_id}/pages/{page_id}/restore", response_model=PageOut)
def restore_page_revision(
    project_id: int,
    page_id: int,
    payload: RestoreIn,
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    from app.models import PageRevision

    project = _owned_project(db, project_id, user)
    page = (
        db.query(Page)
        .filter(Page.id == page_id, Page.project_id == project.id)
        .first()
    )
    if page is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Page not found")
    revision = (
        db.query(PageRevision)
        .filter(PageRevision.id == payload.revision_id, PageRevision.page_id == page.id)
        .first()
    )
    if revision is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Revision not found")
    # Back up the current text before restoring.
    db.add(
        PageRevision(
            page_id=page.id,
            note_text=page.note_text or "",
            actor="system",
        )
    )
    page.note_text = revision.note_text
    page.version += 1
    db.commit()
    db.refresh(page)
    return PageOut.model_validate(page)


@router.get("/{project_id}/structure", response_model=StructureOut)
def get_structure(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models import Section

    _owned_project(db, project_id, user)
    sections = (
        db.query(Section)
        .filter(Section.project_id == project_id)
        .order_by(Section.ord)
        .all()
    )
    out: list[StructureSectionOut] = []
    for section in sections:
        page_ids = [
            row[0]
            for row in db.query(Page.id)
            .filter(Page.project_id == project_id, Page.section_id == section.id)
            .order_by(Page.ord)
            .all()
        ]
        out.append(
            StructureSectionOut(id=section.id, name=section.name, pages=page_ids)
        )
    return StructureOut(sections=out)


@router.post("/{project_id}/suggest-structure", response_model=StructureOut)
def suggest_structure(
    project_id: int,
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    """AI/heuristic section suggestion (unsaved; the user confirms in the UI)."""
    from app.llm.gateway import get_provider
    from app.pipeline.outline import build_deck_outline

    project = _owned_project(db, project_id, user)
    pages = (
        db.query(Page)
        .filter(Page.project_id == project.id)
        .order_by(Page.ord)
        .all()
    )
    if not pages:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No pages")
    texts = [p.raw_text for p in pages]
    outline = build_deck_outline(get_provider(), texts)

    hints = outline.sections if len(outline.sections) > 1 else []
    buckets: list[tuple[str, list[int]]] = []
    if hints:
        for hint in hints:
            start = max(1, min(hint.start, len(pages)))
            end = max(start, min(hint.end, len(pages)))
            ids = [pages[i - 1].id for i in range(start, end + 1)]
            buckets.append((hint.title or f"Section {len(buckets) + 1}", ids))
    else:
        chunk = 4
        for i in range(0, len(pages), chunk):
            ids = [p.id for p in pages[i : i + chunk]]
            buckets.append((f"Section {len(buckets) + 1}", ids))

    # Guarantee every page is covered exactly once.
    covered = {pid for _, ids in buckets for pid in ids}
    missing = [p.id for p in pages if p.id not in covered]
    if missing:
        if buckets:
            buckets[-1][1].extend(missing)
        else:
            buckets.append(("Section 1", missing))
    # De-duplicate while preserving order.
    seen: set[int] = set()
    out_sections: list[StructureSectionOut] = []
    for idx, (name, ids) in enumerate(buckets, start=1):
        clean: list[int] = []
        for pid in ids:
            if pid not in seen:
                seen.add(pid)
                clean.append(pid)
        out_sections.append(StructureSectionOut(id=idx, name=name, pages=clean))
    return StructureOut(sections=out_sections)


@router.put("/{project_id}/structure", response_model=ProjectOut)
def save_structure(
    project_id: int,
    payload: StructureIn,
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    """Atomic section/order/weight save (PRD §4.2). All pages must be covered."""
    from app.models import Section

    project = _owned_project(db, project_id, user)
    pages = (
        db.query(Page)
        .filter(Page.project_id == project.id)
        .all()
    )
    existing_ids = {p.id for p in pages}
    provided_ids: set[int] = set()
    for section in payload.sections:
        for assign in section.pages:
            if assign.page_id in provided_ids:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Duplicate page {assign.page_id}",
                    headers={"X-Error-Code": "INVALID_STRUCTURE"},
                )
            provided_ids.add(assign.page_id)
    if provided_ids != existing_ids:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Structure must cover every page exactly once",
            headers={"X-Error-Code": "INVALID_STRUCTURE"},
        )

    # Replace sections and update page membership/order/weight.
    db.query(Section).filter(Section.project_id == project.id).delete()
    page_by_id = {p.id: p for p in pages}
    for sec_index, section in enumerate(payload.sections, start=1):
        new_section = Section(project_id=project.id, name=section.name, ord=sec_index)
        db.add(new_section)
        db.flush()
        for assign in section.pages:
            target = page_by_id[assign.page_id]
            target.section_id = new_section.id
            target.ord = assign.ord
            target.weight = assign.weight
    db.commit()
    project = _owned_project(db, project_id, user)
    return ProjectOut.model_validate(project)


@router.post("/{project_id}/review", response_model=ReviewOut)
def review_project(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.pipeline.review import analyze

    project = _owned_project(db, project_id, user)
    pages = (
        db.query(Page)
        .filter(Page.project_id == project.id)
        .order_by(Page.ord)
        .all()
    )
    issues = analyze(pages)
    return ReviewOut(
        project_id=project.id,
        clean=not issues,
        issues=[
            {"severity": i.severity, "message": i.message, "pages": i.pages}
            for i in issues
        ],
    )
