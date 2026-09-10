"""Phase 3 tests: style profiles, idempotent webhooks, subscriptions, report."""
from __future__ import annotations

from tests.conftest import _auth, build_pptx, register_verified

PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def test_style_samples_profile_lifecycle_and_project_attach(client):
    token, _ = register_verified(client)
    s1 = client.post(
        "/api/users/me/styles/samples",
        headers=_auth(token),
        json={
            "title": "产品周会",
            "text": "大家好，简单汇报本周进展：完成解析优化，下周接入导出功能。"
            "有问题随时打断，我们逐页过。",
        },
    )
    assert s1.status_code == 201, s1.text
    sid = s1.json()["id"]

    s2 = client.post(
        "/api/users/me/styles/samples",
        headers=_auth(token),
        json={
            "title": "季度汇报",
            "text": "下面汇报本季度整体情况。数据先看结论，细节放附件；"
            "三分钟讲完重点，结尾留一个决策项请大家拍板。",
        },
    )
    assert s2.status_code == 201
    sid2 = s2.json()["id"]

    p = client.post(
        "/api/users/me/styles",
        headers=_auth(token),
        json={"name": "我的汇报风", "sample_ids": [sid, sid2]},
    )
    assert p.status_code == 201, p.text
    prof = p.json()
    assert prof["sample_count"] == 2
    assert len(prof["profile_text"]) >= 20

    listed = client.get("/api/users/me/styles", headers=_auth(token)).json()
    assert any(x["id"] == prof["id"] for x in listed)

    name, data = build_pptx(2)
    up = client.post(
        "/api/projects",
        headers=_auth(token),
        files={"file": (name, data, PPTX_MIME)},
    )
    assert up.status_code == 201, up.text
    pid = up.json()["id"]
    setr = client.put(
        f"/api/projects/{pid}/settings",
        headers=_auth(token),
        json={"style_profile_id": prof["id"]},
    )
    assert setr.status_code == 200, setr.text
    assert setr.json()["style_profile_id"] == prof["id"]

    # Other user's profile cannot be attached.
    token2, _ = register_verified(client)
    other = client.put(
        f"/api/projects/{pid}/settings",
        headers=_auth(token2),
        json={"style_profile_id": prof["id"]},
    )
    assert other.status_code == 422
    assert other.headers.get("X-Error-Code") == "BAD_STYLE_PROFILE"

    # Deleting the profile detaches the project reference.
    d = client.delete(
        f"/api/users/me/styles/{prof['id']}", headers=_auth(token)
    )
    assert d.status_code == 200
    det = client.get(f"/api/projects/{pid}", headers=_auth(token)).json()
    assert det["style_profile_id"] is None


def test_webhook_topup_is_idempotent(client):
    token, email = register_verified(client)
    payload = {
        "provider": "mock",
        "event_id": "evt_test_0001",
        "kind": "topup",
        "amount": 25,
        "currency": "USD",
        "user_email": email,
    }
    r1 = client.post("/api/billing/webhook", json=payload)
    assert r1.status_code == 200, r1.text
    assert r1.json()["balance"] == 25

    r2 = client.post("/api/billing/webhook", json=payload)  # retry-safe
    assert r2.status_code == 200
    assert r2.json()["balance"] == 25

    wallet = client.get("/api/billing/wallet", headers=_auth(token)).json()
    assert wallet["balance"] == 25
    topups = [e for e in wallet["ledger"] if e["kind"] == "topup"]
    assert len(topups) == 1


def test_webhook_unknown_user(client):
    r = client.post(
        "/api/billing/webhook",
        json={
            "provider": "mock",
            "event_id": "evt_0002",
            "kind": "topup",
            "amount": 5,
            "user_email": "nobody@example.com",
        },
    )
    assert r.status_code == 404
    assert r.headers.get("X-Error-Code") == "UNKNOWN_WEBHOOK_USER"


def test_subscribe_and_usage_report(client):
    token, email = register_verified(client)
    sub = client.post(
        "/api/billing/subscribe",
        headers=_auth(token),
        json={"plan_code": "pro", "amount": 30},
    )
    assert sub.status_code == 200, sub.text
    assert sub.json()["balance"] == 30
    me = client.get("/api/auth/me", headers=_auth(token)).json()
    assert me["plan_state"] == "subscriber"

    name, data = build_pptx(2)
    up = client.post(
        "/api/projects",
        headers=_auth(token),
        files={"file": (name, data, PPTX_MIME)},
    )
    pid = up.json()["id"]
    gen = client.post(f"/api/projects/{pid}/generate", headers=_auth(token))
    assert gen.status_code == 200, gen.text

    rep = client.get("/api/billing/report", headers=_auth(token)).json()
    assert rep["projects"] == 1
    assert rep["generated_pages"] == 2
    assert rep["topups_points"] == 30
    assert rep["charges_points"] == 2
    assert rep["balance"] == 28
