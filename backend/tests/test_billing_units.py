"""Unit tests for the idempotent billing ledger (PRD §2.1 / §6)."""
from __future__ import annotations

import pytest

from app.db.base import SessionLocal
from app.models import ApiSession, Job, User
from app.services.billing import (
    ERROR_DUP_JOB,
    ERROR_INSUFFICIENT,
    record_charge,
)
from tests.conftest import register_verified


@pytest.fixture()
def paid_user_id(client):
    token, _ = register_verified(client)
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    user_id = me.json()["id"]
    tp = client.post(
        "/api/billing/topup",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": 10, "currency": "USD"},
    )
    assert tp.status_code == 200
    return user_id


def _session_for_user(user_id: int):
    db = SessionLocal()
    session_row = (
        db.query(ApiSession).filter(ApiSession.user_id == user_id).first()
    )
    user = db.get(User, session_row.user_id)
    return db, user


def test_record_charge_is_idempotent_per_job(client, paid_user_id):
    db, user = _session_for_user(paid_user_id)
    try:
        job = Job(project_id=1, type="generate_page", status="succeeded")
        db.add(job)
        db.commit()
        db.refresh(job)

        record_charge(db, user, job.id, pages=2, per_page_price=1)
        db.refresh(user.wallet)
        assert user.wallet.balance == 8

        # Second charge for the same job must be rejected, not double-debited.
        with pytest.raises(ValueError) as exc:
            record_charge(db, user, job.id, pages=2, per_page_price=1)
        assert str(exc.value) == ERROR_DUP_JOB
        db.refresh(user.wallet)
        assert user.wallet.balance == 8
    finally:
        db.close()


def test_record_charge_rejects_overdraw(client, paid_user_id):
    db, user = _session_for_user(paid_user_id)
    try:
        job = Job(project_id=1, type="generate_whole", status="succeeded")
        db.add(job)
        db.commit()
        db.refresh(job)

        with pytest.raises(ValueError) as exc:
            record_charge(db, user, job.id, pages=99, per_page_price=1)
        assert str(exc.value) == ERROR_INSUFFICIENT
    finally:
        db.close()


def test_counters_mixed_length():
    from app.core.counters import count_chars

    assert count_chars("") == 0
    assert count_chars("hello world") == 2
    assert count_chars("今天是个好日子") == 7
    # Shared counting rule: hanzi chars + latin words.
    assert count_chars("混合 text 一起123") == 6  # 混 合 一 起 (4) + text (1) + 123 (1)
