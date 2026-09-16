"""Deterministic content features (fed to the LLM so it never guesses).

These are computed in code to keep scoring stable and reproducible.
"""
from __future__ import annotations

import re

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]"
)
_TAG_RE = re.compile(r"#([^\s#]+)")
_SENT_SPLIT = re.compile(r"[。！？!?；;\n]+")
_CTA_WORDS = [
    "收藏", "点赞", "评论", "转发", "关注", "分享", "私信", "点击", "订阅",
    "like", "share", "comment", "subscribe", "follow", "save", "click",
]


def content_length(text: str) -> int:
    return len(text.strip())


def detect_language(text: str) -> str:
    sample = text[:2000]
    cjk = len(_CJK_RE.findall(sample))
    latin = len(re.findall(r"[A-Za-z]", sample))
    if cjk == 0 and latin == 0:
        return "unknown"
    return "zh" if cjk >= latin * 0.3 else "en"


def extract_facts(text: str, title: str = "") -> dict:
    body = text.strip()
    paragraphs = [p for p in re.split(r"\n\s*\n|\n", body) if p.strip()]
    sentences = [s for s in _SENT_SPLIT.split(body) if s.strip()]
    cjk_chars = len(_CJK_RE.findall(body))
    facts = {
        "chars": len(body),
        "paragraphs": len(paragraphs),
        "avg_paragraph_chars": round(len(body) / max(len(paragraphs), 1)),
        "sentences": len(sentences),
        "avg_sentence_chars": round(len(body) / max(len(sentences), 1)),
        "emojis": len(_EMOJI_RE.findall(body)),
        "tags": len(_TAG_RE.findall(body)),
        "title_chars": len(title.strip()),
        "questions": body.count("?") + body.count("？"),
        "numbers": len(re.findall(r"\d+(?:\.\d+)?%?", body)),
        "cta_terms": [w for w in _CTA_WORDS if w.lower() in body.lower()],
        "cjk_ratio": round(cjk_chars / max(len(body), 1), 2),
        "language": detect_language(body),
    }
    return facts


def facts_to_prompt(facts: dict) -> str:
    parts = [
        f"chars={facts['chars']}",
        f"paragraphs={facts['paragraphs']}",
        f"avg_para={facts['avg_paragraph_chars']}",
        f"sentences={facts['sentences']}",
        f"avg_sentence={facts['avg_sentence_chars']}",
        f"emojis={facts['emojis']}",
        f"tags={facts['tags']}",
        f"title_len={facts['title_chars']}",
        f"questions={facts['questions']}",
        f"numbers={facts['numbers']}",
        f"ctas={facts['cta_terms']}",
        f"language={facts['language']}",
    ]
    return "; ".join(parts)
