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
    }
)

SECRET_KEYS = frozenset({"llm_api_key"})


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


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * 8}{value[-4:]}"
