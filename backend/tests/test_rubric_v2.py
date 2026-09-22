"""v2 rubric: 7th dimension, weight overrides, archetypes, rewrite audit."""
from __future__ import annotations

import json
import os

from app.content.audit import audit_rewrite
from app.content.rewrite import _verify_changelog
from app.content.rubric import effective_weights, load_rubric
from app.llm.gateway import LLMResult
from tests.conftest import _auth, register_verified

ADMIN = {"Authorization": "Bearer test-admin-token"}


class _StubProvider:
    """Records prompts and returns canned JSON per prompt kind."""

    model = "stub-1"

    def __init__(self, chair_payload: dict | None = None, audit_payload: dict | None = None):
        self.messages: list[tuple[str, str]] = []
        self.chair_payload = chair_payload or {
            "summary": "s",
            "strengths": [],
            "weaknesses": [],
            "top_priorities": [],
            "disagreement": [],
            "must_fix": ["Lead with the outcome."],
        }
        self.audit_payload = audit_payload or {
            "status": "APPROVED",
            "audit_results": {
                "fact_retention": "PASS",
                "zero_new_hallucinations": "PASS",
                "directives_completed": "PASS",
                "tone_and_cleanliness": "PASS",
            },
            "audit_notes": "Looks good.",
            "issues": [],
        }

    def _payload(self, system: str) -> dict:
        if "committee chair" in system:
            return self.chair_payload
        if "Chief Copy Auditor" in system:
            return self.audit_payload
        if "content analyst" in system:
            return {"dimension_notes": []}
        # expert scoring call
        dims = [
            {
                "key": k,
                "evidence": [{"quote": "quote", "location": "para:1"}],
                "rationale": "r",
                "suggestions": [{"issue": "i", "fix": "f", "example": "e"}],
                "band": 3,
                "score": 50,
            }
            for k in (
                "hook",
                "title",
                "rhythm",
                "emotion",
                "social_currency",
                "interaction",
                "domain_logic",
            )
        ]
        return {"summary": "s", "dimensions": dims, "top_priorities": [], "compliance_flags": []}

    def chat(self, system, user, *, json_mode=False, vision=False, images=None):
        self.messages.append((system, user))
        return LLMResult(
            text=json.dumps(self._payload(system), ensure_ascii=False),
            model=self.model,
            input_tokens=10,
            output_tokens=5,
            cost_est=0.0,
        )


def test_rubric_v2_weights_sum_to_one():
    rubric = load_rubric()
    assert rubric.version == "v2"
    assert {d.key for d in rubric.dimensions} >= {"domain_logic"}
    for key in rubric.platforms:
        assert abs(sum(effective_weights(key).values()) - 1.0) < 1e-6, key


def test_effective_weights_apply_overrides():
    base = effective_weights("xiaohongshu")
    bumped = effective_weights("xiaohongshu", {"domain_logic": 0.5})
    assert bumped["domain_logic"] > base["domain_logic"]
    assert abs(sum(bumped.values()) - 1.0) < 1e-3
    # Unknown keys are ignored rather than crashing.
    assert effective_weights("xiaohongshu", {"nope": 1.0}) == base


def test_archetype_block_injected_into_scoring_prompt():
    from app.content import scoring

    scoring.clear_cache()
    provider = _StubProvider()
    scoring.analyze(
        provider,
        title="t",
        content="一段用于测试的文案内容。",
        platform="xiaohongshu",
        lang="zh",
        archetype="quick_social_post",
    )
    assert any("【内容原型】" in user for _system, user in provider.messages)
    assert any("轻量社交帖" in user for _system, user in provider.messages)


def test_scoring_uses_weight_overrides():
    from app.content import scoring

    scoring.clear_cache()
    provider = _StubProvider()
    result = scoring.analyze(
        provider,
        title="t",
        content="一段用于测试的文案内容。",
        platform="xiaohongshu",
        lang="zh",
        weights_overrides={"domain_logic": 0.9},
    )
    weights = {d["key"]: d["weight"] for d in result.dimensions}
    assert weights["domain_logic"] > 0.4


def test_archetype_persisted_and_returned(client):
    token, _ = register_verified(client)
    doc = client.post(
        "/api/documents",
        headers=_auth(token),
        json={
            "title": "t",
            "content": "一段用于测试的文案内容。" * 3,
            "platform": "xiaohongshu",
            "archetype": "industry_case_study",
        },
    ).json()
    assert doc["archetype"] == "industry_case_study"


def test_admin_weights_override_and_reset(client):
    os.environ["ADMIN_TOKEN"] = "test-admin-token"
    try:
        token, _ = register_verified(client)
        before = client.get("/api/documents/platforms", headers=_auth(token)).json()
        base = next(p for p in before["platforms"] if p["key"] == "blog")
        assert base["weights"]["domain_logic"] != 0.5

        saved = client.put(
            "/api/admin/rubric/weights",
            headers=ADMIN,
            json={"weights": {"blog": {"domain_logic": 0.5}}},
        )
        assert saved.status_code == 200, saved.text

        after = client.get("/api/documents/platforms", headers=_auth(token)).json()
        blog = next(p for p in after["platforms"] if p["key"] == "blog")
        assert blog["weights"]["domain_logic"] > base["weights"]["domain_logic"]
        assert abs(sum(blog["weights"].values()) - 1.0) < 1e-3

        bad = client.put(
            "/api/admin/rubric/weights",
            headers=ADMIN,
            json={"weights": {"blog": {"nope": 0.5}}},
        )
        assert bad.status_code == 422
        bad_range = client.put(
            "/api/admin/rubric/weights",
            headers=ADMIN,
            json={"weights": {"blog": {"hook": 3}}},
        )
        assert bad_range.status_code == 422

        reset = client.post("/api/admin/rubric/weights/reset", headers=ADMIN)
        assert reset.status_code == 200
        restored = client.get("/api/documents/platforms", headers=_auth(token)).json()
        blog2 = next(p for p in restored["platforms"] if p["key"] == "blog")
        assert blog2["weights"] == base["weights"]
    finally:
        os.environ.pop("ADMIN_TOKEN", None)


def test_rewrite_audit_reports_only():
    provider = _StubProvider()
    audit, call = audit_rewrite(
        provider,
        original="原文 14.2% 的增长。",
        rewritten="原文 14.2% 的增长，节奏更快。",
        must_fix=["Lead with the outcome."],
    )
    assert call is not None
    assert audit is not None
    assert audit["status"] == "APPROVED"
    assert set(audit["audit_results"]) == {
        "fact_retention",
        "zero_new_hallucinations",
        "directives_completed",
        "tone_and_cleanliness",
    }
    assert "final_clean_copy" not in audit  # report-only


def test_rewrite_audit_skipped_for_mock():
    from app.llm.gateway import MockProvider

    audit, call = audit_rewrite(
        MockProvider(), original="a", rewritten="b", must_fix=[]
    )
    assert audit is None and call is None


def test_changelog_segments_are_verified():
    content = "开头很平。后面还行。"
    rewritten = "先给结论。后面还行。"
    changelog = [
        {"change": "x", "why": "y", "original": "开头很平。", "revised": "先给结论。"},
        {"change": "x", "why": "y", "original": "不存在", "revised": "先给结论。"},
    ]
    out = _verify_changelog(content, rewritten, changelog)
    assert out[0]["verified"] is True
    assert out[1]["verified"] is False
