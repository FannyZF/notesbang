"""Placeholder for a real Merchant-of-Record adapter (e.g. FastSpring).

Left intentionally unimplemented until the seller account is approved; the
shape matches ``PaymentProvider`` so wiring it later is isolated.
"""
from __future__ import annotations

from app.billing.providers.base import CheckoutSession, PaymentProvider


class FastSpringProvider(PaymentProvider):
    name = "fastspring"

    def __init__(self, api_key: str, store_id: str, webhook_secret: str) -> None:
        self.api_key = api_key
        self.store_id = store_id
        self.webhook_secret = webhook_secret

    def create_checkout(
        self, *, user_email: str, points: int, unit_price_usd: float
    ) -> CheckoutSession:  # pragma: no cover - pending account
        raise NotImplementedError("FastSpring adapter pending merchant approval")

    def verify_webhook(self, headers: dict, body: bytes) -> dict:  # pragma: no cover
        raise NotImplementedError("FastSpring adapter pending merchant approval")
