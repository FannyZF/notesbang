"""Global deck outline pass (PRD §4.6, stage 1).

Produces a compact DeckOutline (main message, sections, per-page takeaways,
key data, memory points). For the mock provider (offline) a deterministic
local outline is built from page text; real providers are asked for the
structured JSON from prompts/passes/outline_pass.j2.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from app.core.counters import count_chars
from app.llm.gateway import LLMError, Provider

_MAX_DECK_CHARS = 40_000


@dataclass
class SectionHint:
    title: str
    start: int
    end: int


@dataclass
class DeckOutline:
    main_message: str = ""
    sections: list[SectionHint] = field(default_factory=list)
    takeaways: dict[int, str] = field(default_factory=dict)
    key_data: list[str] = field(default_factory=list)
    memory_points: list[str] = field(default_factory=list)

    def to_context(self) -> str:
        lines = [f"主线：{self.main_message or '（待定）'}"]
        if self.key_data:
            lines.append("关键数据：" + "；".join(self.key_data[:8]))
        for pg in sorted(self.takeaways):
            lines.append(f"p{pg}要点：{self.takeaways[pg]}")
        return "\n".join(lines)


def _first_line(text: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if s:
            return s[:60]
    return text[:60]


def _local_outline(page_texts: list[str]) -> DeckOutline:
    out = DeckOutline(main_message=_first_line(page_texts[0]) if page_texts else "")
    for i, text in enumerate(page_texts, start=1):
        out.takeaways[i] = _first_line(text) or f"第{i}页"
    out.sections = [SectionHint(title="演讲", start=1, end=max(1, len(page_texts)))]
    out.memory_points = list(out.takeaways.values())[:3]
    return out


def build_deck_outline(
    provider: Provider, page_texts: list[str]
) -> DeckOutline:
    if provider.model.startswith("mock"):
        return _local_outline(page_texts)

    deck_text = "\n\n".join(
        f"== p{i} ==\n{t}" for i, t in enumerate(page_texts, start=1)
    )[: _MAX_DECK_CHARS]
    system = (
        "你是演示文稿分析师。通读全部幻灯片文本后，只输出严格 JSON，不要多余内容。"
        "结构：{main_message, sections:[{title,from,to}], "
        "pages:[{page,takeaway,emphasis}], key_data:[], memory_points:[]}"
    )
    user = deck_text
    try:
        res = provider.chat(system, user, json_mode=True)
        data = json.loads(res.text)
    except (LLMError, json.JSONDecodeError, ValueError):
        return _local_outline(page_texts)

    out = DeckOutline(main_message=str(data.get("main_message", "")))
    for s in data.get("sections", []) or []:
        try:
            out.sections.append(
                SectionHint(str(s["title"]), int(s["from"]), int(s["to"]))
            )
        except (KeyError, ValueError, TypeError):
            continue
    for p in data.get("pages", []) or []:
        try:
            out.takeaways[int(p["page"])] = str(p.get("takeaway", ""))
        except (KeyError, ValueError, TypeError):
            continue
    out.key_data = [str(x) for x in data.get("key_data", [])[:8]]
    out.memory_points = [str(x) for x in data.get("memory_points", [])[:6]]
    if not out.sections:
        out.sections = [SectionHint("演讲", 1, max(1, len(page_texts)))]
    for i, text in enumerate(page_texts, start=1):
        out.takeaways.setdefault(i, _first_line(text) or f"第{i}页")
    return out


def estimate_chars(text: str) -> int:
    return count_chars(text)


def sanitize_sections(out: DeckOutline, total_pages: int) -> None:
    cleaned: list[SectionHint] = []
    for s in out.sections:
        start = max(1, min(s.start, total_pages))
        end = max(start, min(s.end, total_pages))
        cleaned.append(SectionHint(s.title, start, end))
    out.sections = cleaned
    if not any(1 <= s.start <= s.end <= total_pages for s in cleaned) or not cleaned:
        out.sections = [SectionHint("演讲", 1, max(1, total_pages))]


_SENT_RE = re.compile(r"[^。！？!?；;\n]*[。！？!?；;\n]|[^。！？!?；;\n]+$")


def summarize(text: str, limit: int = 40) -> str:
    """Tight one-liner used to keep the story trace compact."""
    first = text.strip().splitlines()[0] if text.strip() else ""
    return first[:limit]
