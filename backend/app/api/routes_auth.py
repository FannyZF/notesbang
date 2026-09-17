"""Auth routes: register (email verify) + login."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.security import hash_password, new_token, token_digest, verify_password
from app.db.base import get_db
from app.models import (
    ApiSession,
    EmailVerificationToken,
    Entitlement,
    PasswordResetToken,
    User,
    Wallet,
)
from app.schemas import (
    ChangePasswordIn,
    ForgotIn,
    LoginIn,
    LoginOut,
    PreferencesIn,
    RegisterIn,
    RegisterOut,
    ResendVerificationIn,
    ResetIn,
    UserOut,
)
from app.services.mail import send_reset_link, send_verification_link
from app.services.rate_limit import client_ip, enforce

router = APIRouter(prefix="/auth", tags=["auth"])


def _utcnow_plus(hours: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def _accept_locale(request: Request) -> str:
    return "zh" if "zh" in (request.headers.get("accept-language") or "").lower() else "en"


@router.post("/register", response_model=RegisterOut, status_code=201)
def register(
    payload: RegisterIn,
    request: Request,
    db: Session = Depends(get_db),
):
    settings: Settings = get_settings()
    ip = client_ip(request)
    enforce("register_ip", ip, settings.register_ip_per_hour, 3600)
    enforce("register_burst", ip, settings.register_ip_burst_per_min, 60)

    email = payload.email.lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        plan_state="trial",
    )
    db.add(user)
    db.flush()
    db.add(Entitlement(user_id=user.id, trial_used=False))
    db.add(Wallet(user_id=user.id, balance=0, currency="USD"))
    db.commit()
    db.refresh(user)

    settings: Settings = get_settings()
    token = new_token()
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_digest=token_digest(token),
            expires_at=_utcnow_plus(settings.token_ttl_hours),
        )
    )
    db.commit()
    dev_url = send_verification_link(settings, user.email, token, _accept_locale(request))
    return RegisterOut(
        id=user.id,
        email=user.email,
        email_verified=False,
        plan_state="trial",
        dev_verify_url=dev_url,
        message="Verification email sent",
    )


@router.get("/verify")
def verify_email(
    request: Request,
    token: str = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    settings: Settings = get_settings()
    enforce("verify_ip", client_ip(request), settings.verify_ip_per_hour, 3600)
    row = (
        db.query(EmailVerificationToken)
        .filter(EmailVerificationToken.token_digest == token_digest(token))
        .first()
    )
    if row is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")
    expires_at = row.expires_at
    if expires_at.tzinfo is None:  # SQLite returns naive datetimes
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")
    user = db.get(User, row.user_id)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="User not found")
    user.email_verified = True
    db.delete(row)
    db.commit()
    return {"ok": True, "email": user.email}


@router.post("/login", response_model=LoginOut)
def login(
    payload: LoginIn,
    request: Request,
    db: Session = Depends(get_db),
):
    settings: Settings = get_settings()
    ip = client_ip(request)
    enforce("login_ip", ip, settings.login_ip_per_5min, 300)
    enforce("login_email", payload.email.lower(), 5, 300)
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if getattr(user, "banned", False):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Account suspended",
            headers={"X-Error-Code": "ACCOUNT_BANNED"},
        )
    if not user.email_verified:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Email not verified",
            headers={"X-Error-Code": "EMAIL_NOT_VERIFIED"},
        )
    token = new_token()
    db.add(ApiSession(user_id=user.id, token_digest=token_digest(token)))
    db.commit()
    return LoginOut(token=token, user_id=user.id)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/change-password")
def change_password(
    payload: ChangePasswordIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current, user.password_hash):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
            headers={"X-Error-Code": "WRONG_PASSWORD"},
        )
    user.password_hash = hash_password(payload.new)
    db.commit()
    return {"ok": True}


@router.put("/preferences")
def update_preferences(
    payload: PreferencesIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.notify_on_complete is not None:
        user.notify_on_complete = payload.notify_on_complete
    if payload.locale is not None:
        user.locale = payload.locale
    db.commit()
    return {
        "ok": True,
        "notify_on_complete": user.notify_on_complete,
        "locale": user.locale,
    }


@router.get("/export")
def export_account_data(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download all of the user's data as JSON (GDPR portability)."""
    import json

    from fastapi import Response

    from app.models import Analysis, DimensionScore, Document, LedgerEntry, Rewrite, StyleProfile, StyleSample

    docs = db.query(Document).filter(Document.user_id == user.id).all()
    payload = {
        "account": {
            "email": user.email,
            "plan_state": user.plan_state,
            "email_verified": user.email_verified,
            "locale": user.locale,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "documents": [
            {
                "title": d.title,
                "platform": d.platform,
                "char_count": d.char_count,
                "content": d.content,
                "consent_improve": d.consent_improve,
                "analyses": [
                    {
                        "overall_score": a.overall_score,
                        "summary": a.summary,
                        "dimensions": [
                            {"key": s.key, "band": s.band, "score": s.score}
                            for s in db.query(DimensionScore)
                            .filter(DimensionScore.analysis_id == a.id)
                            .all()
                        ],
                    }
                    for a in db.query(Analysis).filter(Analysis.document_id == d.id).all()
                ],
                "rewrites": [
                    {"kind": r.kind, "content": r.content}
                    for r in db.query(Rewrite).filter(Rewrite.document_id == d.id).all()
                ],
            }
            for d in docs
        ],
        "style_samples": [
            {"title": s.title, "text": s.text}
            for s in db.query(StyleSample).filter(StyleSample.user_id == user.id).all()
        ],
        "style_profiles": [
            {"name": sp.name, "profile_text": sp.profile_text}
            for sp in db.query(StyleProfile)
            .filter(StyleProfile.user_id == user.id)
            .all()
        ],
        "ledger": [
            {"kind": e.kind, "amount": e.amount, "created_at": e.created_at.isoformat()}
            for e in db.query(LedgerEntry)
            .filter(LedgerEntry.user_id == user.id)
            .all()
        ],
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''notesbang-export.json"
        },
    )


@router.delete("/account")
def delete_account(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete the account and all associated data (GDPR erasure)."""
    from app.models import (
        Analysis,
        CorpusFeature,
        DimensionScore,
        Document,
        Feedback,
        LedgerEntry,
        Rewrite,
        StyleProfile,
        StyleSample,
        Subscription,
    )

    doc_ids = [
        row[0] for row in db.query(Document.id).filter(Document.user_id == user.id).all()
    ]
    if doc_ids:
        analysis_ids = [
            row[0]
            for row in db.query(Analysis.id).filter(Analysis.document_id.in_(doc_ids)).all()
        ]
        if analysis_ids:
            db.query(DimensionScore).filter(
                DimensionScore.analysis_id.in_(analysis_ids)
            ).delete(synchronize_session=False)
        db.query(Analysis).filter(Analysis.document_id.in_(doc_ids)).delete(
            synchronize_session=False
        )
        db.query(Rewrite).filter(Rewrite.document_id.in_(doc_ids)).delete(
            synchronize_session=False
        )
        db.query(Feedback).filter(Feedback.document_id.in_(doc_ids)).delete(
            synchronize_session=False
        )
        db.query(CorpusFeature).filter(CorpusFeature.document_id.in_(doc_ids)).delete(
            synchronize_session=False
        )
        db.query(Document).filter(Document.id.in_(doc_ids)).delete(
            synchronize_session=False
        )

    db.query(StyleSample).filter(StyleSample.user_id == user.id).delete()
    db.query(StyleProfile).filter(StyleProfile.user_id == user.id).delete()
    db.query(Subscription).filter(Subscription.user_id == user.id).delete()
    db.query(LedgerEntry).filter(LedgerEntry.user_id == user.id).delete()
    db.query(ApiSession).filter(ApiSession.user_id == user.id).delete()
    db.query(EmailVerificationToken).filter(
        EmailVerificationToken.user_id == user.id
    ).delete()
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id
    ).delete()
    db.query(Entitlement).filter(Entitlement.user_id == user.id).delete()
    db.query(Wallet).filter(Wallet.user_id == user.id).delete()
    db.delete(user)
    db.commit()
    return {"ok": True}


@router.post("/resend-verification")
def resend_verification(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings: Settings = get_settings()
    enforce("verify_email_resend", client_ip(request), settings.verify_ip_per_hour, 3600)
    if user.email_verified:
        return {"ok": True, "already_verified": True}
    db.query(EmailVerificationToken).filter(
        EmailVerificationToken.user_id == user.id
    ).delete()
    db.commit()
    token = new_token()
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_digest=token_digest(token),
            expires_at=_utcnow_plus(settings.token_ttl_hours),
        )
    )
    db.commit()
    dev_url = send_verification_link(settings, user.email, token, user.locale)
    return {"ok": True, "dev_verify_url": dev_url}


@router.post("/resend-verification-email")
def resend_verification_email(
    payload: ResendVerificationIn,
    request: Request,
    db: Session = Depends(get_db),
):
    """Public resend by email (used before the first successful login).

    The response is identical whether or not the account exists to avoid
    account enumeration; a link is only sent to unverified accounts.
    """
    settings: Settings = get_settings()
    enforce("verify_email_resend", client_ip(request), settings.verify_ip_per_hour, 3600)
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is None or user.email_verified:
        return {"ok": True, "dev_verify_url": None}
    db.query(EmailVerificationToken).filter(
        EmailVerificationToken.user_id == user.id
    ).delete()
    db.commit()
    token = new_token()
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_digest=token_digest(token),
            expires_at=_utcnow_plus(settings.token_ttl_hours),
        )
    )
    db.commit()
    dev_url = send_verification_link(settings, user.email, token, _accept_locale(request))
    return {"ok": True, "dev_verify_url": dev_url}


@router.post("/forgot")
def forgot_password(
    payload: ForgotIn,
    request: Request,
    db: Session = Depends(get_db),
):
    """Request a password reset. Response is deliberately the same whether or
    not the account exists (no account enumeration)."""
    settings: Settings = get_settings()
    enforce("forgot_ip", client_ip(request), settings.login_ip_per_5min, 300)
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is None:
        return {"ok": True, "dev_reset_url": None}
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).delete()
    db.commit()
    token = new_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_digest=token_digest(token),
            expires_at=_utcnow_plus(settings.token_ttl_hours),
        )
    )
    db.commit()
    dev_url = send_reset_link(settings, user.email, token, user.locale)
    return {"ok": True, "dev_reset_url": dev_url}


@router.post("/reset")
def reset_password(payload: ResetIn, db: Session = Depends(get_db)):
    row = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_digest == token_digest(payload.token))
        .first()
    )
    if row is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")
    user = db.get(User, row.user_id)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="User not found")
    user.password_hash = hash_password(payload.new)
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).delete()
    db.commit()
    return {"ok": True}
