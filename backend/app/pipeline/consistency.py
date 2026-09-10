"""Cross-page consistency pass (PRD §4.6 stage 3, LLM-enhanced).

Reviews the whole deck's notes for contradictions, repetition, missing
transitions/callbacks and returns targeted rewrites. Mock provider is a no-op
so offline runs stay deterministic and free.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from app.llm.gateway import LLMError, LLMResult, Provider

_SYSTEM = (
    "You are a meticulous presentation editor. Review the full set of speaker "
    "notes for: contradictions across slides, repeated sentences/openings, missing "
    "transitions or callbacks, and inconsistent terminology. Return strict JSON: "
    '{"patches":[{"page": <int>, "revised": "<full revised notes for that slide>"}]}. '
    "Only include slides that genuinely need a fix; keep each revision close to the "
    "original length and language. If everything is consistent, return {\"patches\":[]}."
)


@dataclass
class Patch:
    page: int
    revised: str


def consistency_review(
    provider: Provider,
    pages: list[tuple[int, str]],
    outline_text: str,
) -> tuple[list[Patch], LLMResult | None]:
    """Return (patches, provider_result). Mock provider returns no patches."""
    if provider.model.startswith("mock"):
        return [], None

    deck = "\n\n".join(f"== p{ord_} ==\n{text}" for ord_, text in pages)
    user = f"【大纲】\n{outline_text}\n\n【讲稿】\n{deck}\n\n只输出 JSON。"
    try:
        result = provider.chat(_SYSTEM, user, json_mode=True)
        data = json.loads(result.text)
    except (LLMError, json.JSONDecodeError, ValueError):
        return [], None

    patches: list[Patch] = []
    for item in data.get("patches", []) or []:
        try:
            page = int(item["page"])
            revised = str(item["revised"]).strip()
        except (KeyError, ValueError, TypeError):
            continue
        if revised:
            patches.append(Patch(page=page, revised=revised))
    return patches, result
