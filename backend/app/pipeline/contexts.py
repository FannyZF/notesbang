"""Per-page context assembly + rolling story trace (PRD §4.6 stage 2)."""
from __future__ import annotations

from app.core.counters import count_chars

_TRACE_BUDGET = 1400  # units before oldest entries are compressed away


class StoryTrace:
    """Ever-growing but bounded summary of "what has been said so far"."""

    def __init__(self, budget: int = _TRACE_BUDGET) -> None:
        self._entries: list[str] = []
        self._budget = budget

    def append(self, summary: str) -> None:
        if summary:
            self._entries.append(summary)
        self._trim()

    def _trim(self) -> None:
        while self._entries and count_chars(self.text()) > self._budget:
            merged = "；".join(self._entries[:2])
            self._entries = [merged] + self._entries[2:]

    def text(self) -> str:
        return "；".join(self._entries)


def first_hook(text: str, limit: int = 24) -> str:
    s = text.strip().splitlines()[0] if text.strip() else ""
    return s[:limit]


def build_user_context(
    *,
    outline_text: str,
    trace: StoryTrace,
    prev_notes: str,
    next_hook: str,
    page_no: int,
    total_pages: int,
    section_name: str,
    takeaway: str,
    page_text: str,
    vision_note: str = "",
) -> str:
    blocks = [
        "【全局大纲】",
        outline_text or "（暂无）",
        "",
        "【已讲内容轨迹】",
        trace.text() or "（本页是开场）",
        "",
        "【上一页讲稿】(衔接参考)",
        prev_notes or "（无，本页承接开场）",
        "",
        f"【下一页标题】(预留钩子) {next_hook or '（结尾页）'}",
        "",
        f"【本页内容】第{page_no}/{total_pages}页 · 节「{section_name}」",
        f"本页核心要点：{takeaway}",
        page_text,
    ]
    if vision_note:
        blocks.append(f"[附图说明] {vision_note}")
    blocks.append("")
    blocks.append("请生成本页 speaker notes：")
    return "\n".join(blocks)
