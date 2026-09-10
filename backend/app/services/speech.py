"""Speaking-speed measurement helpers (PRD §4.4).

Speed = known sample length (hanzi for zh, words for en) / measured duration.
No ASR needed: we only ever need the reading duration of a known passage.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.counters import count_chars
from app.models import User

SAMPLE_ZH = (
    "大家好，欢迎来到今天的分享。接下来我会用几分钟时间，向大家介绍这个"
    "方案的核心思路。首先我们看背景，问题很现实；然后我会给出做法与依据，"
    "最后落到下一步行动。整个过程我会尽量讲得通俗、具体。请大家多提意见。"
)

SAMPLE_EN = (
    "Hello everyone, and welcome to today's session. In the next few minutes "
    "I want to walk you through the core idea behind this approach. We will "
    "start with the background and the problem we are solving, then move to "
    "the method and the evidence behind it, and finish with concrete next "
    "steps. Along the way I will keep things practical and easy to follow, "
    "with a few concrete examples. Please feel free to ask questions at any "
    "point. Let us get started."
)


def sample_for(lang: str) -> str:
    return SAMPLE_EN if lang and lang.lower().startswith("en") else SAMPLE_ZH


def sample_chars_for(lang: str) -> int:
    return count_chars(sample_for(lang))


def measure_speed(
    db: Session, user: User, duration_ms: int, lang: str = "zh"
) -> tuple[float, float]:
    """Return (units per second, units per minute) and persist the result."""
    seconds = max(duration_ms / 1000.0, 0.1)
    cps = sample_chars_for(lang) / seconds
    user.measured_speed_cps = round(cps, 3)
    db.commit()
    return round(cps, 3), round(cps * 60, 1)
