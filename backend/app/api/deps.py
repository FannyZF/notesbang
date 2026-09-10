"""Shared FastAPI dependencies."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import token_digest
from app.db.base import get_db
from app.models import ApiSession, User

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token"
        )
    session = (
        db.query(ApiSession)
        .filter(ApiSession.token_digest == token_digest(credentials.credentials))
        .first()
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session"
        )
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    if getattr(user, "banned", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account suspended",
            headers={"X-Error-Code": "ACCOUNT_BANNED"},
        )
    return user


def require_verified(user: User = Depends(get_current_user)) -> User:
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified",
            headers={"X-Error-Code": "EMAIL_NOT_VERIFIED"},
        )
    return user
