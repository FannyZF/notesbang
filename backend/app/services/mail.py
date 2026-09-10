"""Mail delivery with HTML templates.

- "console": prints the link (dev direct-through) and returns it.
- "smtp": sends multipart (plain + HTML) email via SMTP STARTTLS.
Secrets come from env only (PRD §14.7.3).
"""
from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from app.core.config import Settings


def _html(title: str, body: str, cta: str, url: str) -> str:
    return f"""\
<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
            max-width:520px;margin:0 auto;padding:32px 24px;color:#18181b">
  <div style="font-size:13px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:#a1a1aa">
    NotesBang
  </div>
  <h1 style="font-size:22px;margin:12px 0 8px">{title}</h1>
  <p style="font-size:15px;line-height:1.6;color:#52525b;margin:0 0 20px">{body}</p>
  <a href="{url}" style="display:inline-block;background:#18181b;color:#fff;text-decoration:none;
     padding:12px 22px;border-radius:999px;font-size:15px;font-weight:500">{cta}</a>
  <p style="font-size:12px;color:#a1a1aa;margin-top:24px;word-break:break-all">{url}</p>
</div>"""


def _send_smtp(
    settings: Settings, to_email: str, subject: str, text: str, html: str
) -> None:
    if not settings.smtp_host or not settings.smtp_from:
        raise RuntimeError("SMTP_HOST / SMTP_FROM not configured")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr(("NotesBang", settings.smtp_from))
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

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
        text = (
            "Welcome to NotesBang!\n\n"
            "Please confirm your email address to start creating speaker notes:\n"
            f"{url}\n\nThis link expires soon."
        )
        html = _html(
            "Confirm your email",
            "Welcome to NotesBang — confirm your email address to start creating "
            "speaker notes.",
            "Confirm email",
            url,
        )
        _send_smtp(settings, email, "Confirm your NotesBang account", text, html)
        return None
    raise NotImplementedError(f"mail driver '{driver}' not implemented")


def send_reset_link(settings: Settings, email: str, token: str) -> str | None:
    url = f"{settings.app_base_url}/reset?token={token}"
    driver = settings.mail_driver
    if driver == "console":
        print(f"[console-mail] to={email} reset={url}", flush=True)
        return url
    if driver == "smtp":
        text = (
            "We received a request to reset your NotesBang password.\n\n"
            f"Set a new password here:\n{url}\n\nIf you did not ask, ignore this email."
        )
        html = _html(
            "Reset your password",
            "We received a request to reset your NotesBang password. Choose a new "
            "one below. If you did not ask, you can ignore this email.",
            "Set new password",
            url,
        )
        _send_smtp(settings, email, "Reset your NotesBang password", text, html)
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
        text = (
            f'Good news — the speaker notes for "{project_title}" are ready.\n\n'
            f"Open them here:\n{url}"
        )
        html = _html(
            "Your notes are ready",
            f'The speaker notes for "{project_title}" are ready. Open them and give '
            "them a final read.",
            "Open NotesBang",
            url,
        )
        _send_smtp(settings, email, "Your speaker notes are ready", text, html)
        return
    # console/smtp only; other drivers silently skip notifications
