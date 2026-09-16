"""Content-scoring API: documents, analysis (scorecard), rewrites, feedback."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_verified
from app.content import scoring as scoring_mod
from app.content import rewrite as rewrite_mod
from app.content.features import content_length, detect_language, extract_facts
from app.content.rubric import get_platform, load_rubric, platform_label
from app.core.config import get_settings
from app.db.base import get_db
from app.llm.gateway import get_provider
from app.models import Analysis, CorpusFeature, DailyUsage, DimensionScore, Document, Feedback, Rewrite, User
from app.parsers.text_parser import ParseError, parse_upload
from app.schemas import ConsentIn, DocumentPasteIn, FeedbackIn, RewriteIn

router = APIRouter(prefix="/documents", tags=["documents"])

_ALLOWED_EXTS = {".docx", ".txt", ".md", ".markdown"}


def _owned(db: Session, doc_id: int, user: User) -> Document:
    doc = (
        db.query(Document)
        .filter(Document.id == doc_id, Document.user_id == user.id)
        .first()
    )
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


def _cap(content: str) -> str:
    limit = get_settings().content_max_chars
    if content_length(content) > limit:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Content exceeds {limit} characters",
            headers={"X-Error-Code": "CONTENT_TOO_LONG"},
        )
    return content.strip()


def _create(db: Session, user: User, *, title: str, content: str, fmt: str,
            platform: str, consent: bool) -> Document:
    content = _cap(content)
    lang = detect_language(content)
    doc = Document(
        user_id=user.id,
        title=(title or "").strip()[:300] or "Untitled",
        source_format=fmt,
        platform=platform or "auto",
        content=content,
        char_count=content_length(content),
        language=lang,
        consent_improve=consent,
        status="uploaded",
    )
    db.add(doc)
    db.flush()
    if consent:
        db.add(
            CorpusFeature(
                document_id=doc.id,
                platform=doc.platform,
                features_json=json.dumps(extract_facts(content, doc.title), ensure_ascii=False),
            )
        )
    db.commit()
    db.refresh(doc)
    return doc


def _doc_out(doc: Document) -> dict:
    return {
        "id": doc.id,
        "title": doc.title,
        "source_format": doc.source_format,
        "platform": doc.platform,
        "char_count": doc.char_count,
        "language": doc.language,
        "consent_improve": doc.consent_improve,
        "status": doc.status,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


@router.post("", status_code=201)
def create_from_paste(
    payload: DocumentPasteIn,
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    doc = _create(
        db, user,
        title=payload.title, content=payload.content, fmt="paste",
        platform=payload.platform, consent=payload.consent_improve,
    )
    return _doc_out(doc)


@router.post("/upload", status_code=201)
async def create_from_file(
    file: UploadFile = File(...),
    platform: str = Query(default="auto"),
    consent: bool = Query(default=True),
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    from pathlib import Path

    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Supported formats: .docx, .txt, .md",
            headers={"X-Error-Code": "UNSUPPORTED_FORMAT"},
        )
    data = await file.read()
    try:
        title, text = parse_upload(file.filename or "file", data)
    except ParseError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
            headers={"X-Error-Code": "PARSE_FAILED"},
        ) from exc
    doc = _create(
        db, user, title=title, content=text, fmt=ext.lstrip("."),
        platform=platform, consent=consent,
    )
    return _doc_out(doc)


@router.get("")
def list_documents(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Document)
        .filter(Document.user_id == user.id)
        .order_by(Document.created_at.desc())
        .limit(100)
        .all()
    )
    return [_doc_out(d) for d in rows]


@router.get("/platforms")
def list_platforms(lang: str = Query(default="en")):
    rubric = load_rubric()
    return [
        {"key": p.key, "label": p.label_zh if lang.startswith("zh") else p.label_en,
         "weights": p.weights}
        for p in rubric.platforms.values()
    ]


@router.get("/{doc_id}")
def get_document(
    doc_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = _owned(db, doc_id, user)
    out = _doc_out(doc)
    out["content"] = doc.content
    return out


@router.put("/{doc_id}/consent")
def set_consent(
    doc_id: int,
    payload: ConsentIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = _owned(db, doc_id, user)
    doc.consent_improve = payload.consent_improve
    if not payload.consent_improve:
        db.query(CorpusFeature).filter(CorpusFeature.document_id == doc.id).delete()
    db.commit()
    return {"ok": True, "consent_improve": doc.consent_improve}


@router.delete("/{doc_id}")
def delete_document(
    doc_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = _owned(db, doc_id, user)
    db.query(DimensionScore).filter(
        DimensionScore.analysis_id.in_(
            db.query(Analysis.id).filter(Analysis.document_id == doc.id)
        )
    ).delete(synchronize_session=False)
    db.query(Analysis).filter(Analysis.document_id == doc.id).delete(synchronize_session=False)
    db.query(Rewrite).filter(Rewrite.document_id == doc.id).delete(synchronize_session=False)
    db.query(Feedback).filter(Feedback.document_id == doc.id).delete(synchronize_session=False)
    db.query(CorpusFeature).filter(CorpusFeature.document_id == doc.id).delete(synchronize_session=False)
    db.delete(doc)
    db.commit()
    return {"ok": True}


def _quota_check(db: Session, user: User) -> None:
    settings = get_settings()
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    usage = (
        db.query(DailyUsage)
        .filter(DailyUsage.user_id == user.id, DailyUsage.day == day)
        .first()
    )
    used = usage.count if usage else 0
    if used >= settings.free_daily_limit:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily free limit reached ({settings.free_daily_limit})",
            headers={"X-Error-Code": "DAILY_LIMIT_REACHED"},
        )
    if usage is None:
        usage = DailyUsage(user_id=user.id, day=day, count=0)
        db.add(usage)
    usage.count += 1
    db.commit()


def _analysis_out(db: Session, analysis: Analysis) -> dict:
    dims = (
        db.query(DimensionScore)
        .filter(DimensionScore.analysis_id == analysis.id)
        .all()
    )
    return {
        "id": analysis.id,
        "document_id": analysis.document_id,
        "platform": analysis.platform,
        "overall_score": analysis.overall_score,
        "summary": analysis.summary,
        "rubric_version": analysis.rubric_version,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        "dimensions": [
            {
                "key": d.key,
                "label": d.label,
                "band": d.band,
                "score": d.score,
                "weight": d.weight,
                "rationale": d.rationale,
                "evidence": json.loads(d.evidence_json or "[]"),
                "suggestions": json.loads(d.suggestions_json or "[]"),
            }
            for d in dims
        ],
    }


@router.post("/{doc_id}/analyze")
def analyze_document(
    doc_id: int,
    lang: str = Query(default="en"),
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    doc = _owned(db, doc_id, user)
    _quota_check(db, user)
    provider = get_provider()
    try:
        result = scoring_mod.analyze(
            provider,
            title=doc.title,
            content=doc.content,
            platform=doc.platform,
            lang=doc.language if doc.language in ("zh", "en") else lang,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
            headers={"X-Error-Code": "ANALYSIS_FAILED"},
        ) from exc

    analysis = Analysis(
        document_id=doc.id,
        rubric_version=result.rubric_version,
        platform=result.platform,
        overall_score=result.overall_score,
        summary=result.summary,
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_est=result.cost_est,
    )
    db.add(analysis)
    db.flush()
    for d in result.dimensions:
        db.add(
            DimensionScore(
                analysis_id=analysis.id,
                key=d["key"],
                label=d["label"],
                band=d["band"],
                score=d["score"],
                weight=d["weight"],
                rationale=d["rationale"],
                evidence_json=json.dumps(d["evidence"], ensure_ascii=False),
                suggestions_json=json.dumps(d["suggestions"], ensure_ascii=False),
            )
        )
    doc.status = "analyzed"
    db.commit()
    db.refresh(analysis)
    return _analysis_out(db, analysis)


@router.get("/{doc_id}/analysis")
def latest_analysis(
    doc_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = _owned(db, doc_id, user)
    analysis = (
        db.query(Analysis)
        .filter(Analysis.document_id == doc.id)
        .order_by(Analysis.id.desc())
        .first()
    )
    if analysis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not analyzed yet")
    return _analysis_out(db, analysis)


@router.post("/{doc_id}/rewrite")
def rewrite_document(
    doc_id: int,
    payload: RewriteIn,
    lang: str = Query(default="en"),
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    doc = _owned(db, doc_id, user)
    analysis = (
        db.query(Analysis)
        .filter(Analysis.document_id == doc.id)
        .order_by(Analysis.id.desc())
        .first()
    )
    provider = get_provider()
    out_lang = doc.language if doc.language in ("zh", "en") else lang
    try:
        if payload.kind == "full":
            res = rewrite_mod.rewrite_full(
                provider, title=doc.title, content=doc.content, platform=doc.platform,
                lang=out_lang, summary=analysis.summary if analysis else "",
            )
            content, meta = res.rewritten, {"changelog": res.changelog}
        elif payload.kind == "title":
            items = rewrite_mod.title_variants(
                provider, title=doc.title, content=doc.content, platform=doc.platform, lang=out_lang
            )
            content, meta = json.dumps(items, ensure_ascii=False), {}
        elif payload.kind == "hook":
            items = rewrite_mod.hook_variants(
                provider, title=doc.title, content=doc.content, platform=doc.platform, lang=out_lang
            )
            content, meta = json.dumps(items, ensure_ascii=False), {}
        else:
            if not payload.paragraph:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY, detail="paragraph is required"
                )
            revised = rewrite_mod.section_edit(
                provider, paragraph=payload.paragraph, issue=payload.issue or "", lang=out_lang
            )
            content, meta = revised, {}
    except RuntimeError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
            headers={"X-Error-Code": "REWRITE_FAILED"},
        ) from exc

    row = Rewrite(
        document_id=doc.id,
        analysis_id=analysis.id if analysis else None,
        kind=payload.kind,
        content=content,
        meta_json=json.dumps(meta, ensure_ascii=False),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "kind": row.kind, "content": row.content, "meta": meta}


@router.post("/feedback")
def submit_feedback(
    payload: FeedbackIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.add(
        Feedback(
            user_id=user.id,
            document_id=payload.document_id,
            analysis_id=payload.analysis_id,
            target_type=payload.target_type,
            target_ref=payload.target_ref,
            action=payload.action,
        )
    )
    db.commit()
    return {"ok": True}


@router.post("/{doc_id}/outcome")
def record_outcome(
    doc_id: int,
    payload: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Optional real-world outcome (reads/likes/saves) for the corpus label."""
    doc = _owned(db, doc_id, user)
    if not doc.consent_improve:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Consent for improvement is off for this document",
            headers={"X-Error-Code": "CONSENT_OFF"},
        )
    feature = (
        db.query(CorpusFeature)
        .filter(CorpusFeature.document_id == doc.id)
        .first()
    )
    if feature is None:
        feature = CorpusFeature(document_id=doc.id, platform=doc.platform)
        db.add(feature)
    feature.outcome_json = json.dumps(payload, ensure_ascii=False)
    db.commit()
    return {"ok": True}


@router.get("/{doc_id}/export")
def export_document(
    doc_id: int,
    fmt: str = Query(default="md"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = _owned(db, doc_id, user)
    analysis = (
        db.query(Analysis)
        .filter(Analysis.document_id == doc.id)
        .order_by(Analysis.id.desc())
        .first()
    )
    rewrite = (
        db.query(Rewrite)
        .filter(Rewrite.document_id == doc.id, Rewrite.kind == "full")
        .order_by(Rewrite.id.desc())
        .first()
    )
    lines = [f"# {doc.title}", ""]
    if analysis:
        lines.append(f"**Overall score: {analysis.overall_score}/100**")
        lines.append("")
        lines.append(analysis.summary)
        lines.append("")
        for d in _analysis_out(db, analysis)["dimensions"]:
            lines.append(f"## {d['label']} — band {d['band']}/5 (score {d['score']})")
            lines.append(d["rationale"])
            for s in d["suggestions"]:
                lines.append(f"- {s.get('issue','')} → {s.get('fix','')} (e.g. {s.get('example','')})")
            lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Revised copy")
    lines.append("")
    lines.append(rewrite.content if rewrite else "(not rewritten yet)")
    markdown = "\n".join(lines)

    if fmt == "docx":
        from app.exporters.docx_writer import write_docx

        content = write_docx(doc.title, [("Report", markdown)])
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"{doc.id}_report.docx"
    elif fmt == "txt":
        content = markdown.encode("utf-8")
        media = "text/plain"
        filename = f"{doc.id}_report.txt"
    else:
        content = markdown.encode("utf-8")
        media = "text/markdown"
        filename = f"{doc.id}_report.md"
    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
