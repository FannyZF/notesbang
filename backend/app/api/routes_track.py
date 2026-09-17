"""Public, privacy-friendly page-view tracking.

No cookies, no raw IP storage: visitors are counted via a salted hash of
(IP + user agent + month) that cannot be reversed or linked across months.
Requests are best-effort and always answer 200 so tracking can never break
the site.
"""
from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_optional_user
from app.db.base import get_db
from app.models import PageView, User
from app.schemas import TrackIn
from app.services.rate_limit import client_ip, enforce

router = APIRouter(prefix="/track", tags=["track"])

_BOT_RE = re.compile(
    r"bot|crawl|spider|slurp|bingpreview|facebookexternalhit|python-requests|"
    r"httpx|curl|wget|headless|phantom|monitor|uptime|pingdom|semrush|ahrefs",
    re.IGNORECASE,
)


def _is_bot(user_agent: str) -> bool:
    return bool(_BOT_RE.search(user_agent or ""))


def _visitor_hash(ip: str, user_agent: str, day: str) -> str:
    salt = os.getenv("TRACK_SALT", "notesbang")
    # Monthly rotation: stable within a month (accurate UV), unlinkable across.
    month = day[:7]
    raw = f"{salt}|{month}|{ip}|{user_agent}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _referrer_host(referrer: str | None, request: Request) -> str:
    raw = referrer or request.headers.get("referer") or ""
    host = (urlparse(raw).hostname or "").lower()
    return host[:200]


@router.post("")
@router.post("/")
def track_view(
    payload: TrackIn,
    request: Request,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        ip = client_ip(request)
        enforce("track_ip", ip, 120, 60)
        user_agent = request.headers.get("user-agent", "")
        now = datetime.now(timezone.utc)
        day = now.strftime("%Y-%m-%d")
        path = payload.path.strip() or "/"
        if path.startswith("/api") or path.startswith("/_next"):
            return {"ok": True}
        db.add(
            PageView(
                day=day,
                path=path[:200],
                referrer_host=_referrer_host(payload.referrer, request),
                visitor_hash=_visitor_hash(ip, user_agent, day),
                user_id=user.id if user else None,
                is_bot=_is_bot(user_agent),
            )
        )
        db.commit()
    except Exception:  # noqa: BLE001 - tracking must never break the page
        db.rollback()
    return {"ok": True}
