"""Lightweight admin console API (gated by ADMIN_TOKEN).

Provides operational aggregates, a basic user directory with per-user usage
counts, and runtime settings (LLM key/model, daily free limit, cost rates).
Never exposes notes content or secrets in clear text.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core import runtime
from app.core.config import get_settings
from app.db.base import get_db
from app.models import (
    Analysis,
    AppSetting,
    DailyUsage,
    Document,
    Entitlement,
    User,
)
from app.schemas import AdminBanIn, AdminPlanIn, AdminSettingsIn, AdminTestEmailIn

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(request: Request) -> None:
    expected = os.getenv("ADMIN_TOKEN", "")
    auth = request.headers.get("authorization", "")
    supplied = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if not expected:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Admin not configured: set ADMIN_TOKEN in .env and recreate "
                "the api container (docker compose up -d api)"
            ),
            headers={"X-Error-Code": "ADMIN_NOT_CONFIGURED"},
        )
    if supplied != expected:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token",
            headers={"X-Error-Code": "ADMIN_UNAUTHORIZED"},
        )


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _usage_maps(db: Session, user_ids: list[int]) -> dict[str, dict[int, object]]:
    """Per-user counts: documents, analyses, today's usage, last analysis."""
    if not user_ids:
        return {"documents": {}, "analyses": {}, "today": {}, "last": {}}
    documents = dict(
        db.query(Document.user_id, func.count(Document.id))
        .filter(Document.user_id.in_(user_ids))
        .group_by(Document.user_id)
        .all()
    )
    analyses = dict(
        db.query(Document.user_id, func.count(Analysis.id))
        .join(Analysis, Analysis.document_id == Document.id)
        .filter(Document.user_id.in_(user_ids))
        .group_by(Document.user_id)
        .all()
    )
    today = dict(
        db.query(DailyUsage.user_id, DailyUsage.count)
        .filter(DailyUsage.user_id.in_(user_ids), DailyUsage.day == _today())
        .all()
    )
    last = dict(
        db.query(Document.user_id, func.max(Analysis.created_at))
        .join(Analysis, Analysis.document_id == Document.id)
        .filter(Document.user_id.in_(user_ids))
        .group_by(Document.user_id)
        .all()
    )
    return {"documents": documents, "analyses": analyses, "today": today, "last": last}


@router.get("/summary")
def admin_summary(
    request: Request,
    db: Session = Depends(get_db),
):
    _require_admin(request)
    total_users = db.query(func.count(User.id)).scalar() or 0
    verified = db.query(func.count(User.id)).filter(User.email_verified.is_(True)).scalar() or 0
    trial_used = (
        db.query(func.count(Entitlement.id)).filter(Entitlement.trial_used.is_(True)).scalar() or 0
    )
    documents = db.query(func.count(Document.id)).scalar() or 0
    analyses = db.query(func.count(Analysis.id)).scalar() or 0
    analyses_today = (
        db.query(func.coalesce(func.sum(DailyUsage.count), 0))
        .filter(DailyUsage.day == _today())
        .scalar()
        or 0
    )
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    active_users_7d = (
        db.query(func.count(func.distinct(DailyUsage.user_id)))
        .filter(DailyUsage.day >= week_ago)
        .scalar()
        or 0
    )
    llm_cost_usd = float(
        db.query(func.coalesce(func.sum(Analysis.cost_est), 0.0)).scalar() or 0.0
    )
    tokens_in = int(db.query(func.coalesce(func.sum(Analysis.input_tokens), 0)).scalar() or 0)
    tokens_out = int(db.query(func.coalesce(func.sum(Analysis.output_tokens), 0)).scalar() or 0)
    rate = runtime.usd_to_cny(db)
    recent = db.query(User).order_by(User.created_at.desc()).limit(10).all()
    return {
        "totals": {
            "users": total_users,
            "verified_users": verified,
            "trial_used": trial_used,
            "documents": documents,
            "analyses": analyses,
            "analyses_today": int(analyses_today),
            "active_users_7d": active_users_7d,
            "tokens_input": tokens_in,
            "tokens_output": tokens_out,
            "estimated_llm_cost_usd": round(llm_cost_usd, 6),
            "estimated_llm_cost_cny": round(llm_cost_usd * rate, 4),
            "usd_to_cny": rate,
            "free_daily_limit": runtime.free_daily_limit(db),
        },
        "recent_users": [
            {
                "id": u.id,
                "email": u.email,
                "plan": u.plan_state,
                "verified": u.email_verified,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in recent
        ],
    }


@router.get("/settings")
def admin_get_settings(request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    settings = get_settings()
    cfg = runtime.llm_config(db)
    mail = runtime.mail_config(db)
    overrides = {
        row.key: ("***" if row.key in runtime.SECRET_KEYS else row.value)
        for row in db.query(AppSetting).all()
        if row.key in runtime.EDITABLE_KEYS
    }
    return {
        "llm_provider": cfg["provider"],
        "llm_model": cfg["model"],
        "llm_base_url": cfg["base_url"],
        "llm_api_key_set": bool(cfg["api_key"]),
        "llm_api_key_masked": runtime.mask_secret(cfg["api_key"]),
        "free_daily_limit": runtime.free_daily_limit(db),
        "usd_to_cny": runtime.usd_to_cny(db),
        "cost_input_per_m": cfg["cost_input_per_m"],
        "cost_output_per_m": cfg["cost_output_per_m"],
        "mail_driver": mail["mail_driver"],
        "smtp_host": mail["smtp_host"],
        "smtp_port": mail["smtp_port"],
        "smtp_user": mail["smtp_user"],
        "smtp_password_set": bool(mail["smtp_password"]),
        "smtp_password_masked": runtime.mask_secret(mail["smtp_password"]),
        "smtp_from": mail["smtp_from"],
        "smtp_use_tls": mail["smtp_use_tls"],
        "app_base_url": mail["app_base_url"],
        "public_web_url": mail["public_web_url"],
        "warnings": runtime.mail_warnings(db),
        "overrides": overrides,
        "env": {
            "llm_provider": settings.llm_provider,
            "llm_model": settings.deepseek_model,
            "llm_base_url": settings.deepseek_base_url,
            "llm_api_key_set": bool(settings.deepseek_api_key),
            "free_daily_limit": settings.free_daily_limit,
            "usd_to_cny": settings.usd_to_cny,
            "cost_input_per_m": settings.cost_input_per_m,
            "cost_output_per_m": settings.cost_output_per_m,
            "mail_driver": settings.mail_driver,
            "smtp_host": settings.smtp_host,
            "smtp_port": settings.smtp_port,
            "smtp_user": settings.smtp_user,
            "smtp_from": settings.smtp_from,
            "smtp_use_tls": settings.smtp_use_tls,
            "app_base_url": settings.app_base_url,
            "public_web_url": settings.public_web_url,
        },
    }


def _validate_url(key: str, value: str) -> None:
    """Accept an absolute http(s) URL; an empty string clears the override."""
    raw = value.strip()
    if raw == "":
        return
    from urllib.parse import urlparse

    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or " " in raw:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"{key} 必须是完整的 http(s) 地址，例如 https://your-domain"
                "（/verify 属前端页面，请填站点地址，不要填 .../api）"
            ),
        )


@router.put("/settings")
def admin_update_settings(
    payload: AdminSettingsIn,
    request: Request,
    db: Session = Depends(get_db),
):
    _require_admin(request)
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No settings provided"
        )
    for key, value in data.items():
        if key not in runtime.EDITABLE_KEYS:
            continue
        if value is None:
            continue
        if key == "llm_api_key":
            runtime.set_setting(db, key, str(value).strip())
            continue
        if key == "free_daily_limit":
            limit = int(value)
            if limit < 0 or limit > 1000:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="free_daily_limit must be between 0 and 1000",
                )
        if key in ("usd_to_cny", "cost_input_per_m", "cost_output_per_m"):
            if float(value) < 0:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"{key} must be >= 0",
                )
        if key in ("app_base_url", "public_web_url"):
            _validate_url(key, str(value))
        runtime.set_setting(db, key, str(value).strip())
    db.commit()
    return admin_get_settings(request, db)


@router.post("/smtp/test")
def admin_test_email(
    payload: AdminTestEmailIn,
    request: Request,
    db: Session = Depends(get_db),
):
    """Send a probe email using the current (runtime) SMTP settings."""
    _require_admin(request)
    from app.services.mail import send_test_email

    try:
        result = send_test_email(get_settings(), payload.to)
    except Exception as exc:  # noqa: BLE001 - surface SMTP errors to the admin
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=f"SMTP send failed: {exc}",
            headers={"X-Error-Code": "SMTP_SEND_FAILED"},
        ) from exc
    return {**result, "to": payload.to}


@router.post("/users/{user_id}/plan")
def admin_set_plan(
    user_id: int,
    payload: AdminPlanIn,
    request: Request,
    db: Session = Depends(get_db),
):
    _require_admin(request)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    user.plan_state = payload.plan_state
    db.commit()
    return {"ok": True, "plan_state": user.plan_state}


@router.post("/users/{user_id}/ban")
def admin_set_ban(
    user_id: int,
    payload: AdminBanIn,
    request: Request,
    db: Session = Depends(get_db),
):
    _require_admin(request)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    user.banned = payload.banned
    db.commit()
    return {"ok": True, "banned": user.banned}


@router.delete("/users/{user_id}")
def admin_delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Permanently delete a user and all data derived from their documents."""
    _require_admin(request)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")

    from app.models import (
        ApiSession,
        Analysis,
        CorpusFeature,
        DimensionScore,
        Document,
        EmailVerificationToken,
        Entitlement,
        ExpertScore,
        Feedback,
        Job,
        LedgerEntry,
        PasswordResetToken,
        Rewrite,
        StyleProfile,
        StyleSample,
        Subscription,
        Wallet,
    )

    doc_ids = [
        row[0] for row in db.query(Document.id).filter(Document.user_id == user_id).all()
    ]
    analysis_ids: list[int] = []
    if doc_ids:
        analysis_ids = [
            row[0]
            for row in db.query(Analysis.id).filter(Analysis.document_id.in_(doc_ids)).all()
        ]
        if analysis_ids:
            db.query(DimensionScore).filter(
                DimensionScore.analysis_id.in_(analysis_ids)
            ).delete(synchronize_session=False)
            db.query(ExpertScore).filter(
                ExpertScore.analysis_id.in_(analysis_ids)
            ).delete(synchronize_session=False)
        db.query(Analysis).filter(Analysis.document_id.in_(doc_ids)).delete(
            synchronize_session=False
        )
        db.query(Rewrite).filter(Rewrite.document_id.in_(doc_ids)).delete(
            synchronize_session=False
        )
        db.query(CorpusFeature).filter(CorpusFeature.document_id.in_(doc_ids)).delete(
            synchronize_session=False
        )
        db.query(Feedback).filter(Feedback.document_id.in_(doc_ids)).delete(
            synchronize_session=False
        )
        db.query(Job).filter(Job.document_id.in_(doc_ids)).delete(
            synchronize_session=False
        )
        db.query(Document).filter(Document.id.in_(doc_ids)).delete(
            synchronize_session=False
        )

    for model in (
        Feedback,
        DailyUsage,
        ApiSession,
        EmailVerificationToken,
        PasswordResetToken,
        LedgerEntry,
        StyleSample,
        StyleProfile,
        Subscription,
        Entitlement,
        Wallet,
    ):
        db.query(model).filter(model.user_id == user_id).delete(
            synchronize_session=False
        )

    db.delete(user)
    db.commit()
    return {"ok": True, "deleted": user_id}


@router.post("/maintenance/cleanup")
def run_cleanup(
    request: Request,
    ttl_days: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    _require_admin(request)
    from app.services.cleanup import cleanup_expired

    return cleanup_expired(db, ttl_days)


@router.get("/corpus/stats")
def corpus_stats(request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    from app.models import Analysis, CorpusFeature, DimensionScore, Document, Feedback

    total_docs = db.query(func.count(Document.id)).scalar() or 0
    with_consent = (
        db.query(func.count(Document.id))
        .filter(Document.consent_improve.is_(True))
        .scalar()
        or 0
    )
    feature_rows = db.query(CorpusFeature).all()
    outcome_ready = sum(1 for f in feature_rows if f.outcome_json not in ("", "{}"))
    by_platform: dict[str, int] = {}
    for f in feature_rows:
        by_platform[f.platform] = by_platform.get(f.platform, 0) + 1

    score_rows = db.query(Analysis).all()
    avg_overall = round(
        sum(a.overall_score for a in score_rows) / max(len(score_rows), 1), 1
    )
    dim_rows = db.query(DimensionScore).all()
    dim_avg: dict[str, float] = {}
    dim_counts: dict[str, int] = {}
    for d in dim_rows:
        dim_avg[d.key] = dim_avg.get(d.key, 0.0) + d.score
        dim_counts[d.key] = dim_counts.get(d.key, 0) + 1
    dim_avg = {k: round(v / dim_counts[k], 1) for k, v in dim_avg.items()}

    feedback_rows = db.query(Feedback).all()
    by_action: dict[str, int] = {}
    for fb in feedback_rows:
        by_action[fb.action] = by_action.get(fb.action, 0) + 1

    return {
        "documents": total_docs,
        "with_consent": with_consent,
        "corpus_features": len(feature_rows),
        "outcome_ready": outcome_ready,
        "by_platform": by_platform,
        "analyses": len(score_rows),
        "avg_overall_score": avg_overall,
        "dimension_avg_score": dim_avg,
        "feedback": by_action,
    }


@router.get("/corpus/export")
def corpus_export(request: Request, db: Session = Depends(get_db)):
    """Anonymized JSONL: features + per-dimension scores + feedback (no raw text)."""
    _require_admin(request)
    import json as _json

    from app.models import Analysis, CorpusFeature, DimensionScore, Document, Feedback

    docs = db.query(Document).filter(Document.consent_improve.is_(True)).all()
    lines: list[str] = []
    for doc in docs:
        feature = (
            db.query(CorpusFeature).filter(CorpusFeature.document_id == doc.id).first()
        )
        analysis = (
            db.query(Analysis)
            .filter(Analysis.document_id == doc.id)
            .order_by(Analysis.id.desc())
            .first()
        )
        dims = []
        if analysis is not None:
            dims = [
                {"key": d.key, "band": d.band, "score": d.score}
                for d in db.query(DimensionScore)
                .filter(DimensionScore.analysis_id == analysis.id)
                .all()
            ]
        fb = [
            f.action
            for f in db.query(Feedback).filter(Feedback.document_id == doc.id).all()
        ]
        lines.append(
            _json.dumps(
                {
                    "document_id": doc.id,
                    "platform": doc.platform,
                    "language": doc.language,
                    "char_count": doc.char_count,
                    "features": _json.loads(feature.features_json) if feature else {},
                    "outcome": _json.loads(feature.outcome_json) if feature else {},
                    "overall_score": analysis.overall_score if analysis else None,
                    "dimensions": dims,
                    "feedback": fb,
                },
                ensure_ascii=False,
            )
        )
    from fastapi import Response

    body = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
    return Response(
        content=body,
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="corpus.jsonl"'},
    )


@router.get("/users")
def admin_users(
    request: Request,
    email: str | None = Query(default=None),
    limit: int = Query(default=50, le=500),
    db: Session = Depends(get_db),
):
    _require_admin(request)
    q = db.query(User)
    if email:
        q = q.filter(User.email.ilike(f"%{email}%"))
    rows = q.order_by(User.created_at.desc()).limit(limit).all()
    maps = _usage_maps(db, [u.id for u in rows])
    return [
        {
            "id": u.id,
            "email": u.email,
            "plan": u.plan_state,
            "verified": u.email_verified,
            "banned": u.banned,
            "trial_used": bool(u.entitlement and u.entitlement.trial_used),
            "documents": int(maps["documents"].get(u.id, 0)),
            "analyses": int(maps["analyses"].get(u.id, 0)),
            "analyses_today": int(maps["today"].get(u.id, 0)),
            "last_analysis_at": (
                maps["last"][u.id].isoformat()
                if maps["last"].get(u.id) is not None
                else None
            ),
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in rows
    ]
