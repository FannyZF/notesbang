"""Admin operations: settings overrides, usage stats, plan override, ban/unban."""
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


def _make_analysis(client, token):
    doc = client.post(
        "/api/documents",
        headers=_auth(token),
        json={"content": "这是一段用于测试的文案内容。" * 8, "platform": "xiaohongshu"},
    ).json()
    r = client.post(f"/api/documents/{doc['id']}/analyze", headers=_auth(token))
    assert r.status_code == 200, r.text
    return doc


def test_admin_settings_override_free_limit(client):
    os.environ["ADMIN_TOKEN"] = "test-admin-token"
    try:
        token, email = register_verified(client)
        before = client.get("/api/documents/quota", headers=_auth(token)).json()
        assert before["limit"] == 3

        r = client.put(
            "/api/admin/settings",
            headers=_admin_headers(),
            json={"free_daily_limit": 1, "usd_to_cny": 7.0, "llm_api_key": "sk-test-1234"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["free_daily_limit"] == 1
        assert body["usd_to_cny"] == 7.0
        assert body["llm_api_key_set"] is True
        assert "sk-test-1234" not in body["llm_api_key_masked"]

        after = client.get("/api/documents/quota", headers=_auth(token)).json()
        assert after["limit"] == 1

        _make_analysis(client, token)
        doc = client.post(
            "/api/documents",
            headers=_auth(token),
            json={"content": "再来一篇测试文案。" * 10, "platform": "xiaohongshu"},
        ).json()
        blocked = client.post(
            f"/api/documents/{doc['id']}/analyze", headers=_auth(token)
        )
        assert blocked.status_code == 429
        assert blocked.headers.get("X-Error-Code") == "DAILY_LIMIT_REACHED"

        summary = client.get("/api/admin/summary", headers=_admin_headers()).json()
        assert summary["totals"]["free_daily_limit"] == 1
        assert summary["totals"]["analyses_today"] == 1
        assert summary["totals"]["estimated_llm_cost_cny"] >= 0
        assert "topups_points" not in summary["totals"]
    finally:
        os.environ.pop("ADMIN_TOKEN", None)


def test_admin_smtp_settings_and_test_email(client):
    os.environ["ADMIN_TOKEN"] = "test-admin-token"
    try:
        r = client.put(
            "/api/admin/settings",
            headers=_admin_headers(),
            json={
                "mail_driver": "smtp",
                "smtp_host": "smtp.example.com",
                "smtp_port": 465,
                "smtp_user": "mailer",
                "smtp_password": "super-secret",
                "smtp_from": "no-reply@example.com",
                "smtp_use_tls": True,
                "app_base_url": "https://api.example.com",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["smtp_host"] == "smtp.example.com"
        assert body["smtp_port"] == 465
        assert body["smtp_use_tls"] is True
        assert body["smtp_password_set"] is True
        assert "super-secret" not in body["smtp_password_masked"]
        assert body["overrides"]["smtp_password"] == "***"

        # Switch back to console so the probe does not attempt a real connection.
        client.put(
            "/api/admin/settings",
            headers=_admin_headers(),
            json={"mail_driver": "console"},
        )
        probe = client.post(
            "/api/admin/smtp/test",
            headers=_admin_headers(),
            json={"to": "admin@example.com"},
        )
        assert probe.status_code == 200, probe.text
        assert probe.json()["driver"] == "console"
    finally:
        os.environ.pop("ADMIN_TOKEN", None)


def test_admin_url_validation_and_warnings(client, monkeypatch):
    os.environ["ADMIN_TOKEN"] = "test-admin-token"
    try:
        bad = client.put(
            "/api/admin/settings",
            headers=_admin_headers(),
            json={"app_base_url": "not-a-url"},
        )
        assert bad.status_code == 422
        assert "http" in bad.json()["detail"]

        saved = client.put(
            "/api/admin/settings",
            headers=_admin_headers(),
            json={
                "mail_driver": "smtp",
                "app_base_url": "http://localhost:3000",
                "public_web_url": "http://localhost:3000",
                "smtp_host": "smtp.example.com",
                "smtp_from": "no-reply@example.com",
            },
        )
        assert saved.status_code == 200, saved.text
        codes = {w["code"] for w in saved.json()["warnings"]}
        assert "smtp_localhost_link" in codes
        assert "smtp_localhost_web" in codes

        fetched = client.get("/api/admin/settings", headers=_admin_headers()).json()
        assert any(w["code"] == "smtp_localhost_link" for w in fetched["warnings"])

        import app.services.mail as mail_mod

        monkeypatch.setattr(mail_mod, "_send_smtp", lambda *a, **k: None)
        probe = client.post(
            "/api/admin/smtp/test",
            headers=_admin_headers(),
            json={"to": "admin@example.com"},
        )
        assert probe.status_code == 200, probe.text
        assert probe.json()["warning"]

        fixed = client.put(
            "/api/admin/settings",
            headers=_admin_headers(),
            json={
                "app_base_url": "https://notes.example.com",
                "public_web_url": "https://notes.example.com",
            },
        )
        assert fixed.status_code == 200
        assert fixed.json()["warnings"] == []

        ip_link = client.put(
            "/api/admin/settings",
            headers=_admin_headers(),
            json={"app_base_url": "http://203.0.113.10:8088"},
        )
        assert ip_link.status_code == 200
        assert {w["code"] for w in ip_link.json()["warnings"]} == {"smtp_ip_link"}
    finally:
        os.environ.pop("ADMIN_TOKEN", None)


def test_mail_fallback_copy_is_localized():
    from app.services.mail import _FALLBACK, _html

    html_zh = _html("标题", "正文", "按钮", "https://x.example/verify?token=abc", _FALLBACK["zh"])
    assert "按钮无法点击" in html_zh
    assert "https://x.example/verify?token=abc" in html_zh

    html_en = _html("T", "B", "C", "https://x.example/verify?token=abc", _FALLBACK["en"])
    assert "Button not working" in html_en


def test_admin_users_report_usage(client):
    os.environ["ADMIN_TOKEN"] = "test-admin-token"
    try:
        token, email = register_verified(client)
        _make_analysis(client, token)
        rows = client.get("/api/admin/users", headers=_admin_headers()).json()
        row = next(u for u in rows if u["email"] == email)
        assert row["analyses"] == 1
        assert row["documents"] == 1
        assert row["analyses_today"] == 1
        assert row["last_analysis_at"]
        assert row["banned"] is False
        assert "balance" not in row
    finally:
        os.environ.pop("ADMIN_TOKEN", None)


def test_admin_delete_user_cascades(client):
    os.environ["ADMIN_TOKEN"] = "test-admin-token"
    try:
        token, email = register_verified(client)
        _make_analysis(client, token)
        uid = next(
            u["id"]
            for u in client.get("/api/admin/users", headers=_admin_headers()).json()
            if u["email"] == email
        )

        banned = client.post(
            f"/api/admin/users/{uid}/ban",
            headers=_admin_headers(),
            json={"banned": True},
        )
        assert banned.json()["banned"] is True
        row = next(
            u
            for u in client.get("/api/admin/users", headers=_admin_headers()).json()
            if u["id"] == uid
        )
        assert row["banned"] is True

        deleted = client.delete(f"/api/admin/users/{uid}", headers=_admin_headers())
        assert deleted.status_code == 200, deleted.text
        remaining = client.get("/api/admin/users", headers=_admin_headers()).json()
        assert all(u["id"] != uid for u in remaining)

        summary = client.get("/api/admin/summary", headers=_admin_headers()).json()
        assert summary["totals"]["documents"] == 0
        assert summary["totals"]["analyses"] == 0
    finally:
        os.environ.pop("ADMIN_TOKEN", None)
