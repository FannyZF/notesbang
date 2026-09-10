"""Password hashing + opaque token helpers.

Passwords use stdlib PBKDF2-HMAC-SHA256 (no extra binary deps). API sessions
and email-verification links use random opaque tokens; only their SHA-256
digest is stored, so a DB leak does not expose usable credentials.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

_PBKDF2_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return (
        "pbkdf2_sha256$"
        f"{_PBKDF2_ITERATIONS}$"
        f"{base64.b64encode(salt).decode()}$"
        f"{base64.b64encode(digest).decode()}"
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        _, iterations, salt_b64, digest_b64 = encoded.split("$", 3)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, int(iterations)
    )
    return hmac.compare_digest(actual, expected)


def new_token() -> str:
    """Return a raw opaque token; store only its digest."""
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
