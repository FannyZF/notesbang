"""PDF script export (PRD §4.11) with built-in CID CJK font (no font file)."""
from __future__ import annotations

from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))


def write_pdf(title: str, pages: list[tuple[str, str]]) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    title_style = ParagraphStyle(
        "title", fontName="STSong-Light", fontSize=18, leading=26
    )
    head_style = ParagraphStyle(
        "head", fontName="STSong-Light", fontSize=13, leading=18, spaceBefore=8
    )
    body_style = ParagraphStyle(
        "body", fontName="STSong-Light", fontSize=10.5, leading=16
    )
    flow: list = [Paragraph(_esc(title or "Speaker Notes"), title_style), Spacer(1, 8)]
    for header, note in pages:
        flow.append(Paragraph(_esc(header), head_style))
        if note:
            for line in note.splitlines():
                flow.append(Paragraph(_esc(line), body_style))
        flow.append(Spacer(1, 6))
    doc.build(flow)
    buf.seek(0)
    return buf.read()


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
