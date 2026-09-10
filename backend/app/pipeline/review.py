"""Local consistency review heuristics (PRD §4.6 stage 3 — v1 local rules).

Full LLM cross-reference patching is deferred; these rule checks catch the
cheap, high-signal problems: duplicated openings, empty notes, and near-identical
pages. The reviewer endpoint lets users run it before exporting.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.counters import count_chars

_OPENING_SLICE = 30


@dataclass
class Issue:
    severity: str
    message: str
    pages: list[int]


def analyze(pages: list) -> list[Issue]:
    """``pages`` are SQLAlchemy Page-like objects with ord/note_text/raw_text."""
    issues: list[Issue] = []
    ordered = sorted(pages, key=lambda p: p.ord)

    empty = [p.ord for p in ordered if not (p.note_text or "").strip()]
    if empty:
        issues.append(
            Issue("warn", "以下页面还没有生成备注", pages=empty)
        )

    openings: dict[str, list[int]] = {}
    for p in ordered:
        text = (p.note_text or "").strip()
        if not text:
            continue
        key = text[:_OPENING_SLICE].rstrip("。，.,！？!?；;")
        openings.setdefault(key, []).append(p.ord)
    dup = [
        (key, ords)
        for key, ords in openings.items()
        if len(key) >= 8 and len(ords) > 1
    ]
    if dup:
        for key, ords in dup[:5]:
            issues.append(
                Issue(
                    "warn",
                    "多页开场句式高度相似，建议差异化引入",
                    pages=ords,
                )
            )

    seen_keys: set[str] = set()
    for p in ordered:
        body = (p.note_text or "").replace("（本页为 mock", "")
        if not body.strip():
            continue
        key = body[:120]
        if key in seen_keys:
            issues.append(
                Issue("info", "与前面某一页内容几乎相同（可能未按本页重写）", pages=[p.ord])
            )
        seen_keys.add(key)

    stats = [count_chars(p.note_text or "") for p in ordered]
    if len(stats) >= 2:
        longest = max(stats)
        shortest = min(stats)
        if longest and shortest and longest > shortest * 4:
            issues.append(
                Issue(
                    "info",
                    "各页篇幅差异悬殊，可能某页被过度压缩或展开",
                    pages=[],
                )
            )
    return issues
