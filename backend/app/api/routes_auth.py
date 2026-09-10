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
    RegisterIn,
    RegisterOut,
    ResetIn,
    UserOut,
)
from app.services.mail import send_reset_link, send_verification_link
from app.services.rate_limit import client_ip, enforce

router = APIRouter(prefix="/auth", tags=["auth"])


def _utcnow_plus(hours: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)


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
    dev_url = send_verification_link(settings, user.email, token)
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
    dev_url = send_verification_link(settings, user.email, token)
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
    dev_url = send_reset_link(settings, user.email, token)
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
