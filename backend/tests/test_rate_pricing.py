"""Pricing endpoint + server-side rate limiting tests."""
from __future__ import annotations

import os

from app.services.rate_limit import reset


def test_pricing_endpoint(client):
    r = client.get("/api/billing/pricing")
    assert r.status_code == 200
    body = r.json()
    assert body["currency"] == "USD"
    assert body["per_page_points"] == 1
    assert len(body["packs"]) == 4
    # 20 pts / $10 at 1 point-per-page => $0.50 per page.
    assert abs(body["packs"][0]["unit_price"] - 0.5) < 1e-6


def test_register_rate_limited(client):
    os.environ["RATE_LIMIT_ENABLED"] = "true"
    reset()
    try:
        statuses = []
        for i in range(12):
            r = client.post(
                "/api/auth/register",
                json={"email": f"limit-{i}@example.com", "password": "phase0secret"},
            )
            statuses.append(r.status_code)
            if r.status_code == 429:
                assert r.headers.get("X-Error-Code") == "RATE_LIMITED"
                break
        assert 429 in statuses, statuses
    finally:
        os.environ["RATE_LIMIT_ENABLED"] = "false"
        reset()
