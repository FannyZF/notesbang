"""Page-view tracking: public endpoint, bot filtering, admin aggregation."""
from __future__ import annotations

import os

from tests.conftest import _auth, register_verified

ADMIN = {"Authorization": "Bearer test-admin-token"}


def _track(client, path="/", referrer="", ua=None, token=None):
    headers = {}
    if ua:
        headers["User-Agent"] = ua
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.post(
        "/api/track",
        json={"path": path, "referrer": referrer},
        headers=headers or None,
    )


def test_track_is_public_and_counted(client):
    os.environ["ADMIN_TOKEN"] = "test-admin-token"
    try:
        assert _track(client, "/", "https://www.google.com/search").status_code == 200
        assert _track(client, "/studio").status_code == 200
        # Internal/asset paths are ignored.
        assert _track(client, "/api/documents").status_code == 200
        assert _track(client, "/_next/static/x.js").status_code == 200

        body = client.get("/api/admin/traffic?days=7", headers=ADMIN).json()
        assert body["totals"]["pv"] == 2
        assert body["totals"]["uv"] == 1
        assert body["totals"]["pv_today"] == 2
        assert body["totals"]["bots"] == 0

        paths = {p["path"] for p in body["top_paths"]}
        assert paths == {"/", "/studio"}
        hosts = {r["host"] for r in body["top_referrers"]}
        assert "www.google.com" in hosts
        assert len(body["series"]) == 7
        assert body["series"][-1]["pv"] == 2
    finally:
        os.environ.pop("ADMIN_TOKEN", None)


def test_track_filters_bots(client):
    os.environ["ADMIN_TOKEN"] = "test-admin-token"
    try:
        _track(client, "/", ua="Mozilla/5.0 (compatible; Googlebot/2.1)")
        _track(client, "/", ua="Mozilla/5.0 (Windows NT 10.0) Chrome/120")
        body = client.get("/api/admin/traffic", headers=ADMIN).json()
        assert body["totals"]["pv"] == 1
        assert body["totals"]["bots"] == 1
    finally:
        os.environ.pop("ADMIN_TOKEN", None)


def test_track_links_logged_in_user(client):
    os.environ["ADMIN_TOKEN"] = "test-admin-token"
    try:
        token, email = register_verified(client)
        _track(client, "/studio", token=token)

        from app.db.base import SessionLocal
        from app.models import PageView, User

        with SessionLocal() as db:
            user = db.query(User).filter(User.email == email).first()
            row = db.query(PageView).order_by(PageView.id.desc()).first()
            assert row is not None
            assert row.user_id == user.id
    finally:
        os.environ.pop("ADMIN_TOKEN", None)


def test_admin_traffic_requires_token(client):
    os.environ["ADMIN_TOKEN"] = "test-admin-token"
    try:
        assert client.get("/api/admin/traffic").status_code == 401
    finally:
        os.environ.pop("ADMIN_TOKEN", None)
