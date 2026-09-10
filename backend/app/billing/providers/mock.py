"""Mock payment provider (dev/tests): completes checkout immediately."""
from __future__ import annotations

import secrets

from app.billing.providers.base import CheckoutSession, PaymentProvider


class MockProvider(PaymentProvider):
    name = "mock"

    def create_checkout(
        self, *, user_email: str, points: int, unit_price_usd: float
    ) -> CheckoutSession:
        return CheckoutSession(
            reference=f"mock_{secrets.token_urlsafe(10)}",
            amount_usd=round(points * unit_price_usd, 2),
            points=points,
            checkout_url=None,
            completed=True,
        )

    def verify_webhook(self, headers: dict, body: bytes) -> dict:
        import json

        return json.loads(body.decode("utf-8"))
