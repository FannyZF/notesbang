"""Mail template + console driver tests."""
from __future__ import annotations

from app.core.config import Settings
from app.services.mail import _html, send_reset_link, send_verification_link


def test_html_template_contains_cta_and_url():
    html = _html("Title", "Body", "Click", "https://example.com/x?token=abc")
    assert "NotesBang" in html
    assert "Click" in html
    assert "https://example.com/x?token=abc" in html


def test_console_driver_returns_links():
    settings = Settings()
    settings.mail_driver = "console"
    v = send_verification_link(settings, "a@b.com", "tok1")
    assert v and "token=tok1" in v
    r = send_reset_link(settings, "a@b.com", "tok2")
    assert r and "token=tok2" in r
