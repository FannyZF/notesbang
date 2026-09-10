"""Billing routes: wallet, mock top-up, provider webhook, subscription, report."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_verified
from app.db.base import get_db
from app.models import (
    GenerationLog,
    LedgerEntry,
    PricingConfig,
    Project,
    Subscription,
    User,
    Wallet,
)
from app.schemas import (
    CheckoutIn,
    CheckoutOut,
    EntitlementOut,
    LedgerOut,
    SubscribeIn,
    TopupIn,
    UsageReportOut,
    WalletOut,
    WebhookIn,
)
from app.services.billing import (
    ERROR_DUP_EVENT,
    export_locked,
    settle_event,
    topup,
)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/topup", response_model=WalletOut)
def mock_topup(
    payload: TopupIn,
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    """Phase 0/3 dev top-up: credited directly as if a provider confirmed."""
    try:
        wallet = topup(
            db,
            user,
            payload.amount,
            currency=payload.currency,
            provider_event_id=f"mock_{secrets.token_urlsafe(12)}",
            note="dev mock top-up",
        )
    except ValueError as exc:
        if str(exc) == ERROR_DUP_EVENT:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=ERROR_DUP_EVENT)
        raise
    return _wallet_out(db, wallet)


def _apply_subscription(db: Session, user: User, plan_code: str) -> None:
    existing = (
        db.query(Subscription)
        .filter(Subscription.user_id == user.id)
        .order_by(Subscription.id.desc())
        .first()
    )
    if existing is None:
        db.add(
            Subscription(
                user_id=user.id,
                provider="mock",
                status="active",
                plan_code=plan_code,
            )
        )
    else:
        existing.status = "active"
        existing.plan_code = plan_code
    user.plan_state = "subscriber"
    db.commit()


@router.post("/subscribe", response_model=WalletOut)
def mock_subscribe(
    payload: SubscribeIn,
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    """Phase 3 mock subscription: activate plan and credit its first period."""
    event_id = f"mock_sub_{payload.plan_code}_{secrets.token_urlsafe(8)}"
    settle_event(
        db,
        user,
        payload.amount,
        "USD",
        event_id,
        kind="subscription",
        note=f"subscription {payload.plan_code}",
    )
    _apply_subscription(db, user, payload.plan_code)
    return _wallet_out(db, user.wallet)


@router.post("/webhook", response_model=WalletOut)
def provider_webhook(
    payload: WebhookIn,
    db: Session = Depends(get_db),
):
    """Provider webhook (Phase 3). Idempotent on ``event_id``.

    Real providers (FastSpring/Paddle/etc.) verify signatures and translate
    their payloads into this canonical shape; the mock accepts it directly.
    """
    user = db.query(User).filter(User.email == payload.user_email.lower()).first()
    if user is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="Unknown user for webhook",
            headers={"X-Error-Code": "UNKNOWN_WEBHOOK_USER"},
        )
    settle_event(
        db,
        user,
        payload.amount,
        payload.currency,
        payload.event_id,
        kind=payload.kind,
        note=f"{payload.provider} {payload.kind}",
    )
    if payload.kind == "subscription":
        _apply_subscription(db, user, payload.plan_code or "monthly")
    return _wallet_out(db, user.wallet)


PRICING_PACKS = [
    {"points": 10, "usd": 5.0, "label": "Try it out"},
    {"points": 20, "usd": 10.0, "label": "Starter"},
    {"points": 200, "usd": 95.0, "label": "Popular"},
    {"points": 500, "usd": 230.0, "label": "Frequent presenter"},
]


@router.get("/pricing")
def get_pricing(db: Session = Depends(get_db)):
    """Official pricing: per-page point cost + point packages.

    The per-page cost is configurable via pricing_config ('per_page_points')
    or the PRICE_PER_PAGE_POINTS env var — the frontend never hardcodes it.
    """
    from app.core.config import get_settings

    per = get_settings().price_per_page_points
    row = db.query(PricingConfig).filter(PricingConfig.key == "per_page_points").first()
    if row is not None:
        try:
            per = int(row.value)
        except ValueError:
            pass
    packs = [
        {
            **p,
            "unit_price": round((p["usd"] / p["points"]) * per, 4),
        }
        for p in PRICING_PACKS
    ]
    return {"currency": "USD", "per_page_points": per, "packs": packs}


@router.post("/checkout", response_model=CheckoutOut)
def create_checkout(
    payload: CheckoutIn,
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    """Provider-agnostic checkout. Mock completes immediately; a real MoR
    adapter returns a hosted checkout URL for redirect."""
    from app.billing.gateway import get_payment_provider

    unit = round(PRICING_PACKS[0]["usd"] / PRICING_PACKS[0]["points"], 4)
    provider = get_payment_provider()
    session = provider.create_checkout(
        user_email=user.email, points=payload.points, unit_price_usd=unit
    )
    if session.completed:
        wallet = settle_event(
            db,
            user,
            payload.points,
            "USD",
            session.reference,
            kind="topup",
            note=f"checkout {provider.name}",
        )
        return CheckoutOut(
            status="completed", points=payload.points, balance=wallet.balance
        )
    return CheckoutOut(
        status="pending", points=payload.points, checkout_url=session.checkout_url
    )


@router.get("/wallet", response_model=WalletOut)
def get_wallet(
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    wallet = user.wallet
    if wallet is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Wallet not found")
    return _wallet_out(db, wallet)


@router.get("/entitlements", response_model=EntitlementOut)
def get_entitlements(user: User = Depends(require_verified)):
    ent = user.entitlement
    return EntitlementOut(
        trial_used=ent.trial_used if ent else False,
        trial_pages_limit=ent.trial_pages_limit if ent else 2,
        export_locked=export_locked(user),
    )


@router.get("/report", response_model=UsageReportOut)
def usage_report(
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    project_ids = [
        row[0]
        for row in db.query(Project.id).filter(Project.user_id == user.id).all()
    ]
    logs = (
        db.query(GenerationLog).filter(GenerationLog.project_id.in_(project_ids)).all()
        if project_ids
        else []
    )
    entries = db.query(LedgerEntry).filter(LedgerEntry.user_id == user.id).all()
    topups = sum(e.amount for e in entries if e.kind == "topup" and e.amount > 0)
    charges = abs(sum(e.amount for e in entries if e.kind == "charge" and e.amount < 0))
    wallet = user.wallet
    return UsageReportOut(
        user_id=user.id,
        generated_pages=len(logs),
        generation_cost_usd=round(sum(l.cost_est for l in logs), 6),
        topups_points=topups,
        charges_points=charges,
        balance=wallet.balance if wallet else 0,
        projects=len(project_ids),
    )


def _wallet_out(db: Session, wallet: Wallet) -> WalletOut:
    entries = (
        db.query(LedgerEntry)
        .filter(LedgerEntry.user_id == wallet.user_id)
        .order_by(LedgerEntry.created_at.desc())
        .limit(50)
        .all()
    )
    return WalletOut(
        balance=wallet.balance,
        currency=wallet.currency,
        ledger=[LedgerOut.model_validate(e) for e in entries],
    )
