"""LLM provider gateway.

Phase 1 ships a deterministic MockProvider (offline tests/dev) plus a
DeepSeek provider over the OpenAI-compatible chat/completions API. The rest of
the pipeline talks only to the abstract interface, so extra providers (PRD
§1.3 / §15) can be added without touching callers.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings, get_settings


class LLMError(RuntimeError):
    pass


@dataclass
class LLMResult:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_est: float = 0.0


class Provider:
    model: str = ""

    def chat(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        vision: bool = False,
    ) -> LLMResult:
        raise NotImplementedError

    def estimate(self, system: str, user: str, out_text: str) -> LLMResult:
        settings: Settings = get_settings()
        # Rough token estimate; refine after the DeepSeek spike (PRD §15).
        approx = lambda t: max(1, round(len(t) / 1.6))  # noqa: E731
        inp = approx(system) + approx(user)
        out = approx(out_text)
        cost = (
            inp / 1_000_000 * settings.cost_input_per_m
            + out / 1_000_000 * settings.cost_output_per_m
        )
        return LLMResult(
            text=out_text,
            model=self.model,
            input_tokens=inp,
            output_tokens=out,
            cost_est=round(cost, 6),
        )


class MockProvider(Provider):
    """Deterministic stand-in so the whole pipeline runs without an API key."""

    def __init__(self, model: str = "mock-v1") -> None:
        self.model = model

    def chat(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        vision: bool = False,
    ) -> LLMResult:
        if json_mode:
            text = json.dumps({"ok": False, "reason": "mock has no JSON content"}, ensure_ascii=False)
        else:
            # Return something stable; the pipeline's fitter enforces length.
            text = "（本页为 mock 生成的演讲备注草稿）请从本页幻灯片内容出发组织语言，保持连贯并突出要点。"
        return self.estimate(system, user, text)


class DeepSeekProvider(Provider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api_key = settings.deepseek_api_key
        self.base = settings.deepseek_base_url.rstrip("/")
        self.model = settings.deepseek_model
        self.vision_model = settings.deepseek_vision_model

    def chat(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        vision: bool = False,
    ) -> LLMResult:
        if not self.api_key:
            raise LLMError("DEEPSEEK_API_KEY not configured")
        model = self.vision_model if vision else self.model
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.7,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            resp = httpx.post(
                f"{self.base}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=120.0,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMError(f"DeepSeek request failed: {exc}") from exc
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        result = self.estimate(system, user, content)
        result.input_tokens = int(usage.get("prompt_tokens", result.input_tokens))
        result.output_tokens = int(usage.get("completion_tokens", result.output_tokens))
        result.cost_est = round(
            result.input_tokens / 1e6 * self.settings.cost_input_per_m
            + result.output_tokens / 1e6 * self.settings.cost_output_per_m,
            6,
        )
        return result


def get_provider() -> Provider:
    settings = get_settings()
    if settings.llm_provider == "deepseek":
        return DeepSeekProvider(settings)
    return MockProvider()
