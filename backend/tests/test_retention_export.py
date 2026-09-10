"""GDPR export + retention cleanup tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db.base import SessionLocal
from app.models import Page, Project
from app.services.cleanup import cleanup_expired
from tests.conftest import _auth, build_pptx, register_verified

PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def test_account_export(client):
    token, email = register_verified(client)
    name, data = build_pptx(2)
    client.post(
        "/api/projects", headers=_auth(token),
        files={"file": (name, data, PPTX_MIME)},
    )
    r = client.get("/api/auth/export", headers=_auth(token))
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "")
    body = r.json()
    assert body["account"]["email"] == email
    assert len(body["projects"]) == 1
    assert body["projects"][0]["pages"]


def test_retention_cleanup_purges_old_images(client):
    token, _ = register_verified(client)
    name, data = build_pptx(2)
    up = client.post(
        "/api/projects", headers=_auth(token),
        files={"file": (name, data, PPTX_MIME)},
    )
    pid = up.json()["id"]

    db = SessionLocal()
    try:
        project = db.get(Project, pid)
        project.created_at = datetime.now(timezone.utc) - timedelta(days=90)
        page = db.query(Page).filter(Page.project_id == pid).first()
        page.image_key = "old/key.png"
        db.commit()

        result = cleanup_expired(db, ttl_days=30)
        assert result["images"] >= 1
        db.refresh(page)
        assert page.image_key is None
    finally:
        db.close()
