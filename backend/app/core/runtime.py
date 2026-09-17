"""Runtime-adjustable settings (admin console overrides, DB-backed).

Env vars stay the source of defaults; values stored in ``app_settings`` take
precedence so operators can rotate the LLM API key or change the free daily
limit without redeploying.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AppSetting

# Keys the admin console is allowed to override.
EDITABLE_KEYS = frozenset(
    {
        "llm_provider",
        "llm_api_key",
        "llm_model",
        "llm_base_url",
        "free_daily_limit",
        "usd_to_cny",
        "cost_input_per_m",
        "cost_output_per_m",
        "mail_driver",
        "smtp_host",
        "smtp_port",
        "smtp_user",
        "smtp_password",
        "smtp_from",
        "smtp_use_tls",
        "app_base_url",
        "public_web_url",
    }
)

SECRET_KEYS = frozenset({"llm_api_key", "smtp_password"})


def get_setting(db: Session, key: str) -> str | None:
    row = db.get(AppSetting, key)
    return row.value if row is not None else None


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=value))
    else:
        row.value = value
        row.updated_at = datetime.now(timezone.utc)


def _get_float(db: Session, key: str, default: float) -> float:
    raw = get_setting(db, key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _get_int(db: Session, key: str, default: int) -> int:
    return int(_get_float(db, key, float(default)))


def free_daily_limit(db: Session) -> int:
    return max(0, _get_int(db, "free_daily_limit", get_settings().free_daily_limit))


def usd_to_cny(db: Session) -> float:
    return _get_float(db, "usd_to_cny", get_settings().usd_to_cny)


def llm_config(db: Session) -> dict:
    """Effective LLM configuration (runtime override else env default)."""
    settings = get_settings()
    provider = (get_setting(db, "llm_provider") or settings.llm_provider).strip()
    api_key = (get_setting(db, "llm_api_key") or settings.deepseek_api_key).strip()
    base_url = (get_setting(db, "llm_base_url") or settings.deepseek_base_url).strip()
    model = (get_setting(db, "llm_model") or settings.deepseek_model).strip()
    cost_in = _get_float(db, "cost_input_per_m", settings.cost_input_per_m)
    cost_out = _get_float(db, "cost_output_per_m", settings.cost_output_per_m)
    return {
        "provider": provider or "mock",
        "api_key": api_key,
        "base_url": base_url,
        "model": model or settings.deepseek_model,
        "cost_input_per_m": cost_in,
        "cost_output_per_m": cost_out,
    }


def _get_bool(db: Session, key: str, default: bool) -> bool:
    raw = get_setting(db, key)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * 8}{value[-4:]}"


def mail_config(db: Session) -> dict:
    """Effective mail/SMTP configuration (runtime override else env default)."""
    settings = get_settings()
    return {
        "mail_driver": (get_setting(db, "mail_driver") or settings.mail_driver).strip(),
        "smtp_host": (get_setting(db, "smtp_host") or settings.smtp_host).strip(),
        "smtp_port": _get_int(db, "smtp_port", settings.smtp_port),
        "smtp_user": (get_setting(db, "smtp_user") or settings.smtp_user).strip(),
        "smtp_password": (get_setting(db, "smtp_password") or settings.smtp_password),
        "smtp_from": (get_setting(db, "smtp_from") or settings.smtp_from).strip(),
        "smtp_use_tls": _get_bool(db, "smtp_use_tls", settings.smtp_use_tls),
        "app_base_url": (get_setting(db, "app_base_url") or settings.app_base_url).rstrip("/"),
        "public_web_url": (
            get_setting(db, "public_web_url") or settings.public_web_url
        ).rstrip("/"),
    }


_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"})


def _host_of(url: str) -> str:
    from urllib.parse import urlparse

    return (urlparse(url).hostname or "").lower()


def is_local_url(url: str) -> bool:
    """True when the URL points at a loopback/unspecified host (unreachable by mail recipients)."""
    return _host_of(url) in _LOCAL_HOSTS


def _is_ip(host: str) -> bool:
    import ipaddress

    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def mail_warnings(db: Session) -> list[dict]:
    """Non-fatal misconfigurations worth surfacing in the admin console."""
    cfg = mail_config(db)
    warnings: list[dict] = []
    if cfg["mail_driver"] != "smtp":
        return warnings
    if is_local_url(cfg["app_base_url"]):
        warnings.append(
            {
                "code": "smtp_localhost_link",
                "message": (
                    "已启用 SMTP 发信，但邮件链接域名（API base URL）仍是本地地址 "
                    f"（{cfg['app_base_url']}），收件人无法打开验证链接。"
                    "请填写可公开访问的站点地址，例如 https://your-domain。"
                ),
            }
        )
    elif _is_ip(_host_of(cfg["app_base_url"])):
        warnings.append(
            {
                "code": "smtp_ip_link",
                "message": (
                    "邮件链接目前使用 IP 地址 "
                    f"（{cfg['app_base_url']}）。建议改为你的域名（如 https://your-domain），"
                    "否则邮件里的验证链接会暴露 IP、且 IP 变更后即失效。"
                ),
            }
        )
    if is_local_url(cfg["public_web_url"]):
        warnings.append(
            {
                "code": "smtp_localhost_web",
                "message": (
                    "已启用 SMTP 发信，但 Web base URL 仍是本地地址 "
                    f"（{cfg['public_web_url']}）。"
                ),
            }
        )
    return warnings
