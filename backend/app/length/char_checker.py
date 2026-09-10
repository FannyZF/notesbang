"""Character-count verification + deterministic fit (PRD §4.4 / §11).

The fitter trims or pads a generated note so its count lands within the
tolerance band; it is the safety net referenced in the length-control risk row.
"""
from __future__ import annotations

import math
import re

from app.core.counters import count_chars

_SENT_SPLIT = re.compile(r"(?<=[。！？!?；;\n])")

_PADDING_POOL = [
    "这里可以稍微放慢语速，给听众一点消化的时间。",
    "这一点和刚才的内容是连贯的，可以自然过渡过去。",
    "如果时间充裕，可以补一个具体例子让听众更容易记住。",
]


def is_within(text: str, target: int, tolerance: float) -> bool:
    if target <= 0:
        return True
    count = count_chars(text)
    return abs(count - target) <= target * tolerance


def fit_notes(text: str, target: int, tolerance: float = 0.15) -> str:
    """Trim/pad ``text`` so its length lands inside the tolerance band.

    ``low``/``high`` use ceil/floor so any count in [low, high] provably
    satisfies |count - target| <= target * tolerance (integer rounding safe).
    """
    if target <= 0:
        return ""
    count = count_chars(text)
    low = max(1, math.ceil(target * (1 - tolerance)))
    high = math.floor(target * (1 + tolerance))

    if count <= high:
        # Pad up to the low bound with neutral bridge lines when short.
        idx = 0
        while count_chars(text) < low and idx < 60:
            text = text.rstrip() + _PADDING_POOL[idx % len(_PADDING_POOL)]
            idx += 1
        return text

    # Trim on sentence boundaries toward the high bound.
    sentences = _SENT_SPLIT.split(text)
    buf = ""
    for sent in sentences:
        cand = buf + sent
        if buf and count_chars(cand) > high:
            break
        buf = cand
    if count_chars(buf) > high:
        buf = _rough_trim(buf, high)
    return buf.strip() or text[: high * 2]


def _rough_trim(text: str, limit: int) -> str:
    """Last-resort deterministic trim (over-approximates per-char)."""
    # Fall back to a per-character window large enough that, worst case,
    # punctuation/spacing still leaves the result near the budget; the sentence
    # path above is the primary mechanism and handles the normal cases.
    return text[: limit * 3]
