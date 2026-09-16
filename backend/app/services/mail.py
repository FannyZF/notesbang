"""Mail delivery with bilingual (en/zh) HTML templates.

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

_COPY = {
    "verify": {
        "en": ("Confirm your NotesBang account", "Confirm your email", "Confirm email",
               "Welcome to NotesBang — confirm your email address to start scoring and rewriting your copy."),
        "zh": ("确认你的 NotesBang 账号", "确认邮箱", "确认邮箱",
               "欢迎使用 NotesBang —— 请确认邮箱，开始为你的文案评分与改写。"),
    },
    "reset": {
        "en": ("Reset your NotesBang password", "Reset your password", "Set new password",
               "We received a request to reset your password. Choose a new one below."),
        "zh": ("重置你的 NotesBang 密码", "重置密码", "设置新密码",
               "我们收到了重置密码的请求，请在下方设置新密码。"),
    },
    "ready": {
        "en": ("Your report is ready", "Your report is ready", "Open NotesBang",
               "Your copy analysis is ready. Open it and give it a final read."),
        "zh": ("你的报告已就绪", "报告已就绪", "打开 NotesBang",
               "你的文案分析已完成，打开查看并做最后润色。"),
    },
}


def _loc(locale: str | None) -> str:
    return "zh" if (locale or "").lower().startswith("zh") else "en"


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


def _send_smtp(settings: Settings, to_email: str, subject: str, text: str, html: str) -> None:
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


def _send(
    settings: Settings, email: str, token: str, kind: str, path: str, locale: str | None
) -> str | None:
    lang = _loc(locale)
    subject, title, cta, body = _COPY[kind][lang]
    url = f"{settings.app_base_url}{path}?token={token}"
    if settings.mail_driver == "console":
        print(f"[console-mail] to={email} {kind}={url} lang={lang}", flush=True)
        return url
    if settings.mail_driver == "smtp":
        text = f"{body}\n\n{url}"
        _send_smtp(settings, email, subject, text, _html(title, body, cta, url))
        return None
    raise NotImplementedError(f"mail driver '{settings.mail_driver}' not implemented")


def send_verification_link(
    settings: Settings, email: str, token: str, locale: str | None = "en"
) -> str | None:
    return _send(settings, email, token, "verify", "/verify", locale)


def send_reset_link(
    settings: Settings, email: str, token: str, locale: str | None = "en"
) -> str | None:
    return _send(settings, email, token, "reset", "/reset", locale)


def send_generation_ready(
    settings: Settings, email: str, project_title: str, locale: str | None = "en"
) -> None:
    lang = _loc(locale)
    subject, title, cta, body = _COPY["ready"][lang]
    url = f"{settings.public_web_url}/studio"
    if settings.mail_driver == "console":
        print(f"[console-mail] to={email} ready={url} lang={lang}", flush=True)
        return
    if settings.mail_driver == "smtp":
        _send_smtp(settings, email, subject, f"{body}\n\n{url}", _html(title, body, cta, url))
        return
