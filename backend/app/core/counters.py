"""Length/speed counting utilities.

PRD §4.4: Chinese text is counted by hanzi characters, English by words.
Both counters live here so the backend length allocator/verifier and any
frontend replica can share exactly the same rule set.
"""
from __future__ import annotations

import re

_HANZI_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['\u2019-][A-Za-z0-9]+)*")


def count_chars(text: str) -> int:
    """Return display-length in the app's canonical unit for a language.

    ``lang`` may be "auto" (default): counts hanzi + latin words, which is a
    reasonable approximation for mixed notes. Phase 1 will refine per-language
    counting; this is the shared function frontend/backend both use.
    """
    if not text:
        return 0
    hanzi = len(_HANZI_RE.findall(text))
    words = len(_WORD_RE.findall(text))
    # CJK punctuation and whitespace are intentionally not counted.
    return hanzi + words
