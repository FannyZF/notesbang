"""Account deletion (GDPR erasure) test."""
from __future__ import annotations

from tests.conftest import _auth, build_pptx, register_verified

PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def test_delete_account_removes_everything(client):
    token, email = register_verified(client)
    client.post(
        "/api/billing/topup", headers=_auth(token),
        json={"amount": 10, "currency": "USD"},
    )
    name, data = build_pptx(2)
    client.post(
        "/api/projects", headers=_auth(token),
        files={"file": (name, data, PPTX_MIME)},
    )

    d = client.delete("/api/auth/account", headers=_auth(token))
    assert d.status_code == 200, d.text

    # Session and login are gone.
    assert client.get("/api/auth/me", headers=_auth(token)).status_code == 401
    assert (
        client.post("/api/auth/login", json={"email": email, "password": "phase0secret"}).status_code
        == 401
    )
