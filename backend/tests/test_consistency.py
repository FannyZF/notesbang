"""Consistency pass unit tests (mock no-op + JSON patch parsing)."""
from __future__ import annotations

import json

from app.llm.gateway import LLMResult
from app.pipeline.consistency import consistency_review


class FakeProvider:
    model = "fake-v1"

    def __init__(self, patches):
        self._patches = patches

    def chat(self, system, user, *, json_mode=False, vision=False):
        text = json.dumps({"patches": self._patches})
        return LLMResult(text=text, model=self.model, input_tokens=10, output_tokens=5)


class MockLikeProvider:
    model = "mock-v1"

    def chat(self, *a, **k):  # pragma: no cover - should not be called
        raise AssertionError("mock provider must not call the LLM")


def test_mock_provider_is_noop():
    patches, result = consistency_review(MockLikeProvider(), [(1, "a")], "outline")
    assert patches == []
    assert result is None


def test_patches_are_parsed():
    provider = FakeProvider([{"page": 2, "revised": "fixed notes"}])
    patches, result = consistency_review(provider, [(1, "a"), (2, "b")], "outline")
    assert len(patches) == 1
    assert patches[0].page == 2
    assert patches[0].revised == "fixed notes"
    assert result is not None
