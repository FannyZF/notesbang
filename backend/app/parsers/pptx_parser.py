"""PPTX text extraction (PRD §4.1).

Phase 0 extracts per-slide text (title/body/table) so the scaffold can show a
per-page preview. Images/charts rendering and vision analysis land in Phase 1.
"""
from __future__ import annotations

from dataclasses import dataclass

from pptx import Presentation
from pptx.util import Emu


@dataclass
class ParsedPage:
    ord: int
    text: str


def _extract_from_shape(shape) -> list[str]:
    lines: list[str] = []
    if shape.has_text_frame:
        for para in shape.text_frame.paragraphs:
            text = "".join(run.text for run in para.runs).strip()
            if text:
                lines.append(text)
    if shape.has_table:
        table = shape.table
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                lines.append(" | ".join(cells))
    # Group shapes (charts, images, smartart placeholders) are noted but their
    # text is not extractable in Phase 0; vision pass (Phase 1) covers them.
    return lines


def parse_pptx(path: str) -> list[ParsedPage]:
    prs = Presentation(path)
    pages: list[ParsedPage] = []
    for index, slide in enumerate(prs.slides, start=1):
        blocks: list[str] = []
        for shape in slide.shapes:
            blocks.extend(_extract_from_shape(shape))
        text = "\n".join(blocks).strip()
        pages.append(ParsedPage(ord=index, text=text))
    return pages


def count_pptx_pages(path: str) -> int:
    prs = Presentation(path)
    return len(prs.slides._sldIdLst)


def slide_width_in(path: str) -> float:
    """Return slide width in inches; used later for 16:9 detection heuristics."""
    prs = Presentation(path)
    return Emu(prs.slide_width).inches
