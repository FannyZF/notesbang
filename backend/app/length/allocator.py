"""Per-page target-length allocator (PRD §4.4 / §14.1).

Total speaking budget = duration × speed × pacing factor. Each page gets a
share proportional to content weight (density) times user emphasis weight
(1.0 default, ~1.5–2.0 for "重点展开"). A soft floor keeps every page
speakable.
"""
from __future__ import annotations

from app.core.counters import count_chars

_SOFT_FLOOR = 40  # units (hanzi/words) every page keeps at minimum
_DENSITY_CAP = 1800


def content_weight(raw_text: str, emphasis_weight: float = 1.0) -> float:
    density = min(count_chars(raw_text), _DENSITY_CAP) / _DENSITY_CAP
    return (0.5 + 1.0 * density) * emphasis_weight


def allocate_targets(
    page_texts: list[str],
    weights: list[float],
    total_units: int,
    floor: int = _SOFT_FLOOR,
) -> list[int]:
    """Return per-page target unit counts whose sum ~= ``total_units``."""
    n = len(page_texts)
    if n == 0:
        return []
    eff = [
        content_weight(t, w) for t, w in zip(page_texts, weights)
    ]
    total_eff = sum(eff) or 1.0
    raw_targets = [total_units * (e / total_eff) for e in eff]

    if n * floor > total_units:
        # Not enough budget to honour the floor: shrink floors proportionally.
        floor = max(1, total_units // n)

    assigned = [max(floor, round(t)) for t in raw_targets]
    diff = total_units - sum(assigned)
    # Distribute remainder to the heaviest pages to stay close to the target.
    idx_sorted = sorted(range(n), key=lambda i: eff[i], reverse=True)
    i = 0
    while diff != 0:
        j = idx_sorted[i % n]
        if diff > 0:
            assigned[j] += 1
            diff -= 1
        else:
            if assigned[j] > floor:
                assigned[j] -= 1
                diff += 1
        i += 1
    return assigned
