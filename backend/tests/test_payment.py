"""Payment provider framework tests (mock checkout completes offline)."""
from __future__ import annotations

from app.billing.gateway import get_payment_provider
from app.billing.providers.mock import MockProvider
from tests.conftest import _auth, register_verified


def test_mock_provider_amounts():
    p = MockProvider()
    session = p.create_checkout(user_email="a@b.com", points=20, unit_price_usd=0.5)
    assert session.completed is True
    assert session.amount_usd == 10.0
    assert session.reference.startswith("mock_")


def test_checkout_endpoint_credits_mock(client):
    token, _ = register_verified(client)
    r = client.post(
        "/api/billing/checkout",
        headers=_auth(token),
        json={"points": 10},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert body["balance"] == 10

    # Registry defaults to mock.
    assert get_payment_provider().name == "mock"
