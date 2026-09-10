"""Admin operations: points adjustment, plan override, ban/unban."""
from __future__ import annotations

import os

from tests.conftest import _auth, register_verified


def _admin_headers():
    return {"Authorization": "Bearer test-admin-token"}


def test_admin_adjust_plan_ban(client):
    os.environ["ADMIN_TOKEN"] = "test-admin-token"
    try:
        token, email = register_verified(client)
        users = client.get("/api/admin/users", headers=_admin_headers()).json()
        uid = next(u["id"] for u in users if u["email"] == email)

        pts = client.post(
            f"/api/admin/users/{uid}/points",
            headers=_admin_headers(),
            json={"delta": 50, "note": "goodwill"},
        )
        assert pts.status_code == 200, pts.text
        assert pts.json()["balance"] == 50

        plan = client.post(
            f"/api/admin/users/{uid}/plan",
            headers=_admin_headers(),
            json={"plan_state": "subscriber"},
        )
        assert plan.json()["plan_state"] == "subscriber"

        ban = client.post(
            f"/api/admin/users/{uid}/ban",
            headers=_admin_headers(),
            json={"banned": True},
        )
        assert ban.json()["banned"] is True
        assert (
            client.post(
                "/api/auth/login", json={"email": email, "password": "phase0secret"}
            ).status_code
            == 403
        )

        client.post(
            f"/api/admin/users/{uid}/ban",
            headers=_admin_headers(),
            json={"banned": False},
        )
        assert (
            client.post(
                "/api/auth/login", json={"email": email, "password": "phase0secret"}
            ).status_code
            == 200
        )
    finally:
        os.environ.pop("ADMIN_TOKEN", None)


def test_notification_preferences(client):
    token, _ = register_verified(client)
    r = client.put(
        "/api/auth/preferences",
        headers=_auth(token),
        json={"notify_on_complete": False},
    )
    assert r.status_code == 200
    assert r.json()["notify_on_complete"] is False
    me = client.get("/api/auth/me", headers=_auth(token)).json()
    assert me["notify_on_complete"] is False
