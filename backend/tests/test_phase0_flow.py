"""Auth + trial + billing + parse integration tests (Phase 0 DoD)."""
from __future__ import annotations

from tests.conftest import _auth, build_pptx, register_verified


def test_register_verify_login_me(client):
    token, email = register_verified(client)
    me = client.get("/api/auth/me", headers=_auth(token))
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == email
    assert body["email_verified"] is True
    assert body["plan_state"] == "trial"


def test_unverified_cannot_upload(client):
    r = client.post(
        "/api/auth/register",
        json={"email": "late@example.com", "password": "phase0secret"},
    )
    assert r.status_code == 201
    rl = client.post(
        "/api/auth/login", json={"email": "late@example.com", "password": "phase0secret"}
    )
    token = rl.json()["token"]
    fname, data = build_pptx(2)
    up = client.post(
        "/api/projects",
        headers=_auth(token),
        files={"file": (fname, data, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
    )
    assert up.status_code == 403
    assert up.headers.get("X-Error-Code") == "EMAIL_NOT_VERIFIED"


def test_trial_parse_preview_and_export_lock(client):
    token, _ = register_verified(client)
    fname, data = build_pptx(2)

    up = client.post(
        "/api/projects",
        headers=_auth(token),
        files={"file": (fname, data, "application/octet-stream")},
    )
    assert up.status_code == 201, up.text
    project = up.json()
    assert project["status"] == "parsed"
    assert len(project["pages"]) == 2
    assert "Hello" in project["pages"][0]["raw_text"]
    assert project["pages"][0]["raw_text"] != ""

    # Trial export is locked server-side.
    ex = client.post(f"/api/projects/{project['id']}/export", headers=_auth(token))
    assert ex.status_code == 402
    assert ex.headers.get("X-Error-Code") == "EXPORT_LOCKED"

    ent = client.get("/api/billing/entitlements", headers=_auth(token)).json()
    assert ent["export_locked"] is True


def test_trial_3_page_upload_rejected(client):
    token, _ = register_verified(client)
    fname, data = build_pptx(3, prefix="big")
    up = client.post(
        "/api/projects",
        headers=_auth(token),
        files={"file": (fname, data, "application/octet-stream")},
    )
    assert up.status_code == 403
    assert up.headers.get("X-Error-Code") == "TRIAL_PAGE_LIMIT_EXCEEDED"


def test_topup_unlocks_export_and_bigger_uploads(client):
    token, _ = register_verified(client)

    # Reject big upload before funding.
    big_name, big_data = build_pptx(3, prefix="big")
    up = client.post(
        "/api/projects",
        headers=_auth(token),
        files={"file": (big_name, big_data, "application/octet-stream")},
    )
    assert up.status_code == 403

    # Mock top-up credits the wallet.
    tp = client.post(
        "/api/billing/topup", headers=_auth(token), json={"amount": 20, "currency": "USD"}
    )
    assert tp.status_code == 200
    wallet = tp.json()
    assert wallet["balance"] == 20
    assert any(e["kind"] == "topup" for e in wallet["ledger"])

    ent = client.get("/api/billing/entitlements", headers=_auth(token)).json()
    assert ent["export_locked"] is False

    # Bigger upload allowed now.
    up = client.post(
        "/api/projects",
        headers=_auth(token),
        files={"file": (big_name, big_data, "application/octet-stream")},
    )
    assert up.status_code == 201
    pid = up.json()["id"]
    assert len(up.json()["pages"]) == 3

    # Export gate requires generated notes; without them -> 422 NOTES_MISSING.
    ex = client.post(f"/api/projects/{pid}/export", headers=_auth(token))
    assert ex.status_code == 422
    assert ex.headers.get("X-Error-Code") == "NOTES_MISSING"

    # Generate (charges 3) then export succeeds as a real download.
    gen = client.post(f"/api/projects/{pid}/generate", headers=_auth(token))
    assert gen.status_code == 200, gen.text
    assert gen.json()["charged_points"] == 3
    ex = client.post(f"/api/projects/{pid}/export", headers=_auth(token))
    assert ex.status_code == 200
    assert "presentationml" in ex.headers["content-type"]
    assert "_notes.pptx" in ex.headers["content-disposition"]

    got = client.get(f"/api/projects/{pid}", headers=_auth(token))
    assert got.status_code == 200
