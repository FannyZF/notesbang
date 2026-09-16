"""Golden-set regression harness for scoring stability.

Default (mock) run asserts determinism + evidence integrity. Set
``RUN_GOLDEN=1`` with a real API key to run the model-backed metrics.
"""
from __future__ import annotations

import os

import pytest

from app.content import scoring as scoring_mod
from app.content.scoring import clear_cache
from app.llm.gateway import get_provider

GOLDEN = [
    {
        "platform": "xiaohongshu",
        "title": "3个月0到1万粉",
        "content": "我用3个月把粉丝从0做到1万，方法只有3步。\n第一，先写结论；"
        "第二，用具体数字；第三，结尾提问。你最常用哪一招？评论区告诉我。",
    },
    {
        "platform": "wechat",
        "title": "内容创作的三个误区",
        "content": "很多人写文章只看阅读量，忽略了结构。第一，标题决定打开率；"
        "第二，首屏决定读完率；第三，结尾决定转发率。你怎么看？",
    },
    {
        "platform": "linkedin",
        "title": "Why your posts flop",
        "content": "Most posts fail in the first line. Lead with the outcome, add one "
        "number, then ask a question. What is your go-to opener?",
    },
]


def test_golden_mock_is_deterministic():
    provider = get_provider()
    assert provider.model.startswith("mock")
    for case in GOLDEN:
        clear_cache()
        first = scoring_mod.analyze(
            provider, title=case["title"], content=case["content"],
            platform=case["platform"], lang="zh" if case["platform"] != "linkedin" else "en",
        )
        clear_cache()
        second = scoring_mod.analyze(
            provider, title=case["title"], content=case["content"],
            platform=case["platform"], lang="zh" if case["platform"] != "linkedin" else "en",
        )
        assert first.overall_score == second.overall_score
        for dim in first.dimensions:
            assert 1 <= dim["band"] <= 5
            for ev in dim["evidence"]:
                assert ev["quote"] in case["content"], "evidence must be a real substring"


@pytest.mark.skipif(
    os.getenv("RUN_GOLDEN") != "1" or not os.getenv("DEEPSEEK_API_KEY"),
    reason="real-model golden run is opt-in (RUN_GOLDEN=1 + DEEPSEEK_API_KEY)",
)
def test_golden_real_model_band_consistency():
    """Same doc scored twice should land on the same bands (stability gate)."""
    provider = get_provider()
    case = GOLDEN[0]
    clear_cache()
    a = scoring_mod.analyze(
        provider, title=case["title"], content=case["content"],
        platform=case["platform"], lang="zh",
    )
    clear_cache()
    b = scoring_mod.analyze(
        provider, title=case["title"], content=case["content"],
        platform=case["platform"], lang="zh",
    )
    bands_a = {d["key"]: d["band"] for d in a.dimensions}
    bands_b = {d["key"]: d["band"] for d in b.dimensions}
    agree = sum(1 for k in bands_a if bands_a[k] == bands_b.get(k))
    assert agree / max(len(bands_a), 1) >= 0.9, (bands_a, bands_b)
