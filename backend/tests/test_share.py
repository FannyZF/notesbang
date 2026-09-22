"""Shareable read-only scorecards: creation, sanitization, rotation, revoke."""
from __future__ import annotations

from tests.conftest import _auth, register_verified

SAMPLE = "我用3个月把粉丝从0做到1万，方法只有3步。你最常用哪一招？评论区告诉我。"


def _doc_with_analysis(client, token):
    doc = client.post(
        "/api/documents",
        headers=_auth(token),
        json={"title": "增长", "content": SAMPLE, "platform": "xiaohongshu"},
    ).json()
    client.post(f"/api/documents/{doc['id']}/analyze", headers=_auth(token))
    return doc


def test_share_roundtrip_and_sanitization(client):
    token, _ = register_verified(client)
    doc = _doc_with_analysis(client, token)

    created = client.post(
        f"/api/documents/{doc['id']}/share",
        headers=_auth(token),
        json={"include_content": False},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert "/s/" in body["url"]
    share_token = body["token"]

    # Public, no auth required.
    public = client.get(f"/api/share/{share_token}")
    assert public.status_code == 200
    data = public.json()
    assert data["overall_score"] == 50
    assert len(data["dimensions"]) == 7
    assert data["include_content"] is False
    assert "content" not in data
    assert all(d["evidence"] == [] for d in data["dimensions"])
    # No identity leakage.
    assert "document_id" not in data
    assert "id" not in data
    assert data["views"] == 1

    # Status endpoint reports it without leaking the token.
    status_body = client.get(
        f"/api/documents/{doc['id']}/share", headers=_auth(token)
    ).json()
    assert status_body["shared"] is True
    assert status_body["url"] is None


def test_share_include_content_opt_in(client):
    token, _ = register_verified(client)
    doc = _doc_with_analysis(client, token)
    created = client.post(
        f"/api/documents/{doc['id']}/share",
        headers=_auth(token),
        json={"include_content": True},
    ).json()
    data = client.get(f"/api/share/{created['token']}").json()
    assert data["include_content"] is True
    assert data["content"] == SAMPLE
    assert any(d["evidence"] for d in data["dimensions"])


def test_share_rotates_and_revokes(client):
    token, _ = register_verified(client)
    doc = _doc_with_analysis(client, token)
    first = client.post(
        f"/api/documents/{doc['id']}/share", headers=_auth(token), json={}
    ).json()
    second = client.post(
        f"/api/documents/{doc['id']}/share", headers=_auth(token), json={}
    ).json()
    assert client.get(f"/api/share/{first['token']}").status_code == 404
    assert client.get(f"/api/share/{second['token']}").status_code == 200

    assert (
        client.delete(
            f"/api/documents/{doc['id']}/share", headers=_auth(token)
        ).status_code
        == 200
    )
    assert client.get(f"/api/share/{second['token']}").status_code == 404


def test_share_requires_analysis_and_ownership(client):
    token, _ = register_verified(client)
    doc = client.post(
        "/api/documents",
        headers=_auth(token),
        json={"title": "t", "content": SAMPLE, "platform": "xiaohongshu"},
    ).json()
    blocked = client.post(
        f"/api/documents/{doc['id']}/share", headers=_auth(token), json={}
    )
    assert blocked.status_code == 409

    other, _ = register_verified(client)
    assert (
        client.post(
            f"/api/documents/{doc['id']}/share", headers=_auth(other), json={}
        ).status_code
        == 404
    )


def test_unknown_share_token_is_404(client):
    assert client.get("/api/share/nope-not-a-token").status_code == 404
