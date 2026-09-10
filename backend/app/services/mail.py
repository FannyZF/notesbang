"""Mail delivery.

- "console": prints the verification link (dev direct-through) and returns it.
- "smtp": sends a real email via SMTP (STARTTLS), configured from env vars.
Secrets come from env only (PRD §14.7.3).
"""
from __future__ import annotations

import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

from app.core.config import Settings


def _send_smtp(settings: Settings, to_email: str, subject: str, body: str) -> None:
    if not settings.smtp_host or not settings.smtp_from:
        raise RuntimeError("SMTP_HOST / SMTP_FROM not configured")
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr(("NotesBang", settings.smtp_from))
    msg["To"] = to_email

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
        server.ehlo()
        if settings.smtp_use_tls:
            server.starttls()
            server.ehlo()
        if settings.smtp_user and settings.smtp_password:
            server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_from, [to_email], msg.as_string())


def send_verification_link(settings: Settings, email: str, token: str) -> str | None:
    url = f"{settings.app_base_url}/verify?token={token}"
    driver = settings.mail_driver
    if driver == "console":
        print(f"[console-mail] to={email} verify={url}", flush=True)
        return url
    if driver == "smtp":
        subject = "Confirm your NotesBang account"
        body = (
            "Welcome to NotesBang!\n\n"
            "Please confirm your email address to start creating speaker notes:\n"
            f"{url}\n\n"
            "This link expires soon. If you did not sign up, you can ignore this email."
        )
        _send_smtp(settings, email, subject, body)
        return None
    raise NotImplementedError(f"mail driver '{driver}' not implemented")


def send_reset_link(settings: Settings, email: str, token: str) -> str | None:
    url = f"{settings.app_base_url}/reset?token={token}"
    driver = settings.mail_driver
    if driver == "console":
        print(f"[console-mail] to={email} reset={url}", flush=True)
        return url
    if driver == "smtp":
        subject = "Reset your NotesBang password"
        body = (
            "We received a request to reset your NotesBang password.\n\n"
            f"Set a new password here:\n{url}\n\n"
            "This link expires soon. If you did not ask to reset it, you can ignore "
            "this email."
        )
        _send_smtp(settings, email, subject, body)
        return None
    raise NotImplementedError(f"mail driver '{driver}' not implemented")


def send_generation_ready(
    settings: Settings, email: str, project_title: str
) -> None:
    """Best-effort "your notes are ready" notification (no-op if misconfigured)."""
    url = f"{settings.public_web_url}/app"
    if settings.mail_driver == "console":
        print(
            f"[console-mail] to={email} notes-ready project={project_title!r} {url}",
            flush=True,
        )
        return
    if settings.mail_driver == "smtp":
        subject = "Your speaker notes are ready"
        body = (
            f'Good news — the speaker notes for "{project_title}" are ready.\n\n'
            f"Open them here:\n{url}\n\nYou can close this window; the notes are saved "
            "to your account."
        )
        _send_smtp(settings, email, subject, body)
        return
    # console/smtp only; other drivers silently skip notifications
