"""Payment provider registry (selected via PAYMENT_PROVIDER)."""
from __future__ import annotations

from functools import lru_cache

from app.billing.providers.base import PaymentProvider
from app.billing.providers.mock import MockProvider
from app.core.config import get_settings


@lru_cache
def get_payment_provider() -> PaymentProvider:
    settings = get_settings()
    if settings.payment_provider == "fastspring":
        from app.billing.providers.fastspring import FastSpringProvider

        return FastSpringProvider(
            api_key=settings.fastspring_api_key,
            store_id=settings.fastspring_store_id,
            webhook_secret=settings.fastspring_webhook_secret,
        )
    return MockProvider()
