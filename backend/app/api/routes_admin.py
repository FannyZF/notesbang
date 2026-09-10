"""Lightweight admin console API (gated by ADMIN_TOKEN).

Provides operational aggregates and a basic user directory — never exposes
notes content, wallet internals, or secrets. Deeper admin (refunds, plans)
can build on this later.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models import (
    Entitlement,
    GenerationLog,
    LedgerEntry,
    Page,
    Project,
    User,
)
from app.schemas import AdminBanIn, AdminPlanIn, AdminPointsIn

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(request: Request) -> None:
    expected = os.getenv("ADMIN_TOKEN", "")
    auth = request.headers.get("authorization", "")
    supplied = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if not expected:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin not configured",
            headers={"X-Error-Code": "ADMIN_NOT_CONFIGURED"},
        )
    if supplied != expected:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token",
            headers={"X-Error-Code": "ADMIN_UNAUTHORIZED"},
        )


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
    projects = db.query(func.count(Project.id)).scalar() or 0
    generated_pages = (
        db.query(func.count(Page.id)).filter(Page.note_text != "").scalar() or 0
    )
    topups = db.query(LedgerEntry).filter(LedgerEntry.kind == "topup").all()
    charges = db.query(LedgerEntry).filter(LedgerEntry.kind == "charge").all()
    llm_cost = (
        db.query(func.coalesce(func.sum(GenerationLog.cost_est), 0.0)).scalar() or 0.0
    )
    recent = (
        db.query(User)
        .order_by(User.created_at.desc())
        .limit(10)
        .all()
    )
    return {
        "totals": {
            "users": total_users,
            "verified_users": verified,
            "trial_used": trial_used,
            "projects": projects,
            "generated_pages": generated_pages,
            "topups_points": sum(e.amount for e in topups if e.amount > 0),
            "charges_points": abs(sum(e.amount for e in charges if e.amount < 0)),
            "estimated_llm_cost_usd": round(float(llm_cost), 6),
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


@router.post("/users/{user_id}/points")
def admin_adjust_points(
    user_id: int,
    payload: AdminPointsIn,
    request: Request,
    db: Session = Depends(get_db),
):
    _require_admin(request)
    import secrets

    from sqlalchemy import update

    from app.models import LedgerEntry, Wallet

    user = db.get(User, user_id)
    if user is None or user.wallet is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    new_balance = user.wallet.balance + payload.delta
    if new_balance < 0:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Balance cannot go negative"
        )
    db.execute(
        update(Wallet)
        .where(Wallet.id == user.wallet.id)
        .values(balance=new_balance, version=Wallet.version + 1)
    )
    db.add(
        LedgerEntry(
            user_id=user.id,
            kind="refund" if payload.delta > 0 else "charge",
            amount=payload.delta,
            provider_event_id=f"admin_{secrets.token_urlsafe(8)}",
            note=payload.note or "admin adjustment",
        )
    )
    db.commit()
    return {"ok": True, "balance": new_balance}


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


@router.post("/maintenance/cleanup")
def run_cleanup(
    request: Request,
    ttl_days: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    _require_admin(request)
    from app.services.cleanup import cleanup_expired

    return cleanup_expired(db, ttl_days)


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
    return [
        {
            "id": u.id,
            "email": u.email,
            "plan": u.plan_state,
            "verified": u.email_verified,
            "balance": u.wallet.balance if u.wallet else 0,
            "trial_used": bool(u.entitlement and u.entitlement.trial_used),
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in rows
    ]
