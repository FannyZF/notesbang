"""GDPR export + retention cleanup tests (content-scoring product)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db.base import SessionLocal
from app.models import Document
from app.services.cleanup import cleanup_expired
from tests.conftest import _auth, register_verified

SAMPLE = "我用3个月把粉丝从0做到1万，方法只有3步。你最常用哪一招？评论区告诉我。"


def _make_doc(client, token):
    return client.post(
        "/api/documents",
        headers=_auth(token),
        json={"title": "增长", "content": SAMPLE, "platform": "xiaohongshu"},
    ).json()


def test_account_export(client):
    token, email = register_verified(client)
    _make_doc(client, token)
    r = client.get("/api/auth/export", headers=_auth(token))
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "")
    body = r.json()
    assert body["account"]["email"] == email
    assert len(body["documents"]) == 1
    assert body["documents"][0]["content"]


def test_retention_cleanup_purges_old_documents(client):
    token, _ = register_verified(client)
    doc = _make_doc(client, token)

    db = SessionLocal()
    try:
        row = db.get(Document, doc["id"])
        row.created_at = datetime.now(timezone.utc) - timedelta(days=90)
        db.commit()
        result = cleanup_expired(db, ttl_days=30)
        assert result["documents"] >= 1
        assert db.get(Document, doc["id"]) is None
    finally:
        db.close()
