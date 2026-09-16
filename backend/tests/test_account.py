"""Account deletion (GDPR erasure) test — content-scoring product."""
from __future__ import annotations

from tests.conftest import _auth, register_verified

SAMPLE = "我用3个月把粉丝从0做到1万，方法只有3步。你最常用哪一招？评论区告诉我。"


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
