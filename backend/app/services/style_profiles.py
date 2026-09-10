"""Style-profile extraction (PRD §4.8).

Samples are distilled by the LLM into a compact, prompt-injectable profile text
so per-page prompts stay cheap and stable. Mock provider returns a neutral
deterministic profile so the full flow is testable offline.
"""
from __future__ import annotations

import json

from app.llm.gateway import LLMError, Provider

_SYSTEM = (
    "你是演讲风格分析专家。阅读用户的历史讲稿样例，提炼其稳定风格，输出严格 JSON"
    "（不要多余字符），结构：{\"profile_text\": string, \"tone\": string, "
    "\"sentence\": string, \"structure\": string}。"
    "其中 profile_text 是可直接插入演讲稿生成 prompt 的一段话（中文，2~6 句），"
    "涵盖：语气、句长偏好、连接词与开场过渡习惯、结构套路；不要复述样例内容本身。"
)

_FALLBACK_TEXT = (
    "用户个人风格：语气自然流畅、表达清晰直接，善用具体例证；倾向中等偏短句，"
    "避免堆砌术语；常用设问与小结帮助听众跟随；开场简洁、结尾收束有力。"
    "（基于样例自动抽取，可手动调整。）"
)

_MAX_SAMPLE_CHARS = 12_000


def extract_profile(provider: Provider, samples: list[str]) -> tuple[str, str]:
    """Return (profile_text, raw_json_str)."""
    joined = "\n\n".join(samples)[: _MAX_SAMPLE_CHARS]
    if provider.model.startswith("mock"):
        return _FALLBACK_TEXT, "{}"
    try:
        result = provider.chat(_SYSTEM, joined, json_mode=True)
        data = json.loads(result.text)
        text = str(data.get("profile_text", "")).strip()
        if len(text) >= 20:
            return text, result.text
    except (LLMError, json.JSONDecodeError, ValueError):
        pass
    return _FALLBACK_TEXT, "{}"
