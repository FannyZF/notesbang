"""Payment provider interface.

Real providers (FastSpring/Paddle/...) implement ``create_checkout`` and
``verify_webhook``; the mock provider runs the full flow offline so the app and
tests work without a merchant account.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CheckoutSession:
    reference: str
    amount_usd: float
    points: int
    checkout_url: str | None = None
    completed: bool = False


class PaymentProvider:
    name = "base"

    def create_checkout(
        self, *, user_email: str, points: int, unit_price_usd: float
    ) -> CheckoutSession:
        raise NotImplementedError

    def verify_webhook(self, headers: dict, body: bytes) -> dict:
        """Return a canonical event dict or raise ValueError."""
        raise NotImplementedError
