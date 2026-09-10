"""Billing / wallet / entitlement service logic.

Phase 0 implements the idempotent ledger + mock top-up so the money loop can be
verified end-to-end without a real payment provider (PRD §2.4).
"""
from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import LedgerEntry, User, Wallet

ERROR_INSUFFICIENT = "INSUFFICIENT_BALANCE"
ERROR_DUP_EVENT = "DUPLICATE_PROVIDER_EVENT"
ERROR_DUP_JOB = "DUPLICATE_JOB_CHARGE"


def is_paid(user: User) -> bool:
    return user.wallet is not None and user.wallet.balance > 0


def export_locked(user: User) -> bool:
    """Trial results cannot be exported until the user tops up (PRD §2.2)."""
    return not is_paid(user)


def topup(
    db: Session,
    user: User,
    amount: int,
    currency: str = "USD",
    provider_event_id: str | None = None,
    note: str = "mock top-up",
) -> Wallet:
    settings: Settings = get_settings()
    db.add(
        LedgerEntry(
            user_id=user.id,
            kind="topup",
            amount=amount,
            provider_event_id=provider_event_id,
            note=note,
        )
    )
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ValueError(ERROR_DUP_EVENT)
    wallet = user.wallet
    db.execute(
        update(Wallet)
        .where(Wallet.id == wallet.id)
        .values(balance=Wallet.balance + amount, version=Wallet.version + 1)
    )
    db.commit()
    db.refresh(wallet)
    settings  # reserved for later per-unit pricing config reads
    return wallet


def record_charge(
    db: Session,
    user: User,
    job_id: int,
    pages: int,
    per_page_price: int | None = None,
) -> None:
    """Idempotently charge ``pages * price`` points for a finished job.

    Raises ValueError(ERROR_DUP_JOB) if the job was already charged, or
    ValueError(ERROR_INSUFFICIENT) if the balance cannot cover the charge.
    """
    price = per_page_price or get_settings().price_per_page_points
    amount = pages * price
    wallet = user.wallet
    if wallet is None:
        raise ValueError(ERROR_INSUFFICIENT)

    result = db.execute(
        update(Wallet)
        .where(Wallet.id == wallet.id, Wallet.balance >= amount)
        .values(balance=Wallet.balance - amount, version=Wallet.version + 1)
    )
    if result.rowcount != 1:
        raise ValueError(ERROR_INSUFFICIENT)

    db.add(
        LedgerEntry(
            user_id=user.id,
            kind="charge",
            amount=-amount,
            job_id=job_id,
            note=f"generated {pages} page(s)",
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError(ERROR_DUP_JOB)


def settle_event(
    db: Session,
    user: User,
    amount: int,
    currency: str,
    event_id: str,
    kind: str = "topup",
    note: str | None = None,
) -> Wallet:
    """Idempotently credit a provider event (webhook retry safe)."""
    existing = (
        db.query(LedgerEntry).filter(LedgerEntry.provider_event_id == event_id).first()
    )
    if existing is not None:
        return user.wallet
    try:
        wallet = topup(
            db,
            user,
            amount,
            currency=currency,
            provider_event_id=event_id,
            note=note or f"{kind} via {event_id[:8]}",
        )
        db.refresh(user)
    except ValueError:
        db.refresh(user)
        wallet = user.wallet
    return wallet


def can_upload_pages(user: User, page_count: int) -> tuple[bool, str]:
    """Upload page-count policy for Phase 0.

    - Trial user (trial not used): at most ``trial_pages_limit`` pages.
    - Paid user (balance > 0): at most the configured ``page_limit``.
    - Trial already used and unpaid: top up first.
    """
    settings = get_settings()
    if is_paid(user):
        return page_count <= settings.page_limit, "PAGE_LIMIT_EXCEEDED"
    if not user.entitlement or not user.entitlement.trial_used:
        return page_count <= settings.trial_pages_limit, "TRIAL_PAGE_LIMIT_EXCEEDED"
    return False, "TRIAL_USED_NEED_FUNDS"


# ---------- generation budget (Phase 1) ----------

def can_generate_unpaid(user: User, kind: str) -> tuple[bool, str]:
    """Unpaid users may generate within their one-shot trial budget.

    kind == "page": one single-page regeneration; kind == "whole": the trial
    generation itself plus one whole-deck regeneration (PRD §2.2).
    """
    if is_paid(user):
        return True, ""
    ent = user.entitlement
    if ent is None:
        return False, "TRIAL_LIMIT_REACHED"
    if not ent.trial_used:
        return True, ""
    if kind == "page":
        ok = ent.trial_page_regens_used < ent.trial_regens_per_page
        return ok, "" if ok else "TRIAL_LIMIT_REACHED"
    ok = ent.trial_whole_regens_used < ent.trial_regens_whole
    return ok, "" if ok else "TRIAL_LIMIT_REACHED"


def consume_generation_budget(db: Session, user: User, kind: str) -> None:
    """Mark trial budget used. Paid users are charged separately via
    ``record_charge`` and consume no budget here."""
    if is_paid(user):
        return
    ent = user.entitlement
    if ent is None:
        return
    if kind == "page":
        ent.trial_page_regens_used += 1
    elif not ent.trial_used:
        ent.trial_used = True
    else:
        ent.trial_whole_regens_used += 1
    db.commit()


def required_price_pages(user: User, page_count: int) -> int:
    return page_count * (get_settings().price_per_page_points if is_paid(user) else 0)
