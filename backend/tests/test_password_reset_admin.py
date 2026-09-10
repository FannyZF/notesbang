"""Password reset + admin gateway tests."""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from tests.conftest import _auth, register_verified


def test_forgot_and_reset_password(client):
    token, email = register_verified(client)
    # Existing email -> dev reset url returned by console driver.
    forgot = client.post("/api/auth/forgot", json={"email": email})
    assert forgot.status_code == 200
    dev = forgot.json()["dev_reset_url"]
    assert dev is not None
    reset_token = parse_qs(urlparse(dev).query)["token"][0]

    # Unknown email returns ok but no url (no enumeration).
    ghost = client.post("/api/auth/forgot", json={"email": "nobody@example.com"})
    assert ghost.status_code == 200
    assert ghost.json()["dev_reset_url"] is None

    r = client.post(
        "/api/auth/reset", json={"token": reset_token, "new": "reset-pass-99"}
    )
    assert r.status_code == 200

    ok = client.post("/api/auth/login", json={"email": email, "password": "reset-pass-99"})
    assert ok.status_code == 200
    old = client.post("/api/auth/login", json={"email": email, "password": "phase0secret"})
    assert old.status_code == 401

    # Token is single-use now.
    again = client.post("/api/auth/reset", json={"token": reset_token, "new": "reset-pass-99"})
    assert again.status_code == 400


def test_admin_endpoints_gate_when_not_configured(client):
    # With no ADMIN_TOKEN configured the console returns 503.
    r = client.get("/api/admin/summary")
    assert r.status_code == 503
    assert r.headers.get("X-Error-Code") == "ADMIN_NOT_CONFIGURED"
