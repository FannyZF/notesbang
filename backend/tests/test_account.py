"""Account deletion (GDPR erasure) + email-verification gating tests."""
from __future__ import annotations

import uuid
from urllib.parse import parse_qs, urlparse

from tests.conftest import _auth, register_verified

SAMPLE = "我用3个月把粉丝从0做到1万，方法只有3步。你最常用哪一招？评论区告诉我。"


def test_login_requires_verified_email(client):
    email = f"unverified-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post(
        "/api/auth/register", json={"email": email, "password": "phase0secret"}
    )
    assert r.status_code == 201, r.text

    blocked = client.post(
        "/api/auth/login", json={"email": email, "password": "phase0secret"}
    )
    assert blocked.status_code == 403
    assert blocked.headers.get("X-Error-Code") == "EMAIL_NOT_VERIFIED"

    resent = client.post("/api/auth/resend-verification-email", json={"email": email})
    assert resent.status_code == 200, resent.text
    dev_url = resent.json()["dev_verify_url"]
    assert dev_url
    token = parse_qs(urlparse(dev_url).query)["token"][0]

    verified = client.get("/api/auth/verify", params={"token": token})
    assert verified.status_code == 200, verified.text
    assert verified.json()["email"] == email

    ok = client.post("/api/auth/login", json={"email": email, "password": "phase0secret"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["token"]


def test_resend_verification_does_not_enumerate(client):
    r = client.post(
        "/api/auth/resend-verification-email", json={"email": "nobody@example.com"}
    )
    assert r.status_code == 200
    assert r.json()["dev_verify_url"] is None


def test_delete_account_removes_everything(client):
    token, email = register_verified(client)
    doc = client.post(
        "/api/documents",
        headers=_auth(token),
        json={"title": "增长", "content": SAMPLE, "platform": "xiaohongshu"},
    ).json()
    client.post(f"/api/documents/{doc['id']}/analyze", headers=_auth(token))

    d = client.delete("/api/auth/account", headers=_auth(token))
    assert d.status_code == 200, d.text

    assert client.get("/api/auth/me", headers=_auth(token)).status_code == 401
    assert (
        client.post("/api/auth/login", json={"email": email, "password": "phase0secret"}).status_code
        == 401
    )
