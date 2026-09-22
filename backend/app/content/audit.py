"""LLM rewrite auditor (report-only).

One extra model call that checks a rewritten copy against the source and the
committee's must-fix list. It NEVER rewrites the copy: it only reports a
PASS/FAIL per check plus notes, so the editor stage stays the single author of
the text. Failures are swallowed — auditing must never break a rewrite.
"""
from __future__ import annotations

import json

from app.llm.gateway import LLMError, Provider

_AUDIT_SYSTEM = (
    "You are the Chief Copy Auditor. You perform automated quality assurance on an "
    "edited draft against the source text and the committee's must-fix list. You "
    "NEVER rewrite the copy; you only report findings.\n"
    "Audit these four checks and answer PASS or FAIL for each:\n"
    "1. fact_retention: did the revision alter, generalize or drop any number, "
    "name or core claim from the source?\n"
    "2. zero_new_hallucinations: did the editor introduce any metric or claim that "
    "is not in the source?\n"
    "3. directives_completed: was EVERY must-fix item fully addressed?\n"
    "4. tone_and_cleanliness: does the text contain banned filler, rhetorical "
    "openers, buzzwords or synthetic enthusiasm?\n"
    "If any check fails, status is REJECTED; otherwise APPROVED. Do not rewrite "
    "anything: report only.\n"
    'Output strict JSON: {"status":"APPROVED|REJECTED","audit_results":'
    '{"fact_retention":"PASS|FAIL","zero_new_hallucinations":"PASS|FAIL",'
    '"directives_completed":"PASS|FAIL","tone_and_cleanliness":"PASS|FAIL"},'
    '"audit_notes":"...","issues":[{"check":"...","quote":"...","note":"..."}]}'
)


def audit_enabled() -> bool:
    """Read the admin runtime toggle, falling back to the env default."""
    try:
        from app.core import runtime
        from app.db.base import SessionLocal

        with SessionLocal() as db:
            return runtime.audit_llm_enabled(db)
    except Exception:  # noqa: BLE001 - never break a rewrite over config lookup
        from app.core.config import get_settings

        return get_settings().audit_llm_enabled


def audit_rewrite(
    provider: Provider,
    *,
    original: str,
    rewritten: str,
    must_fix: list[str] | None = None,
    lang: str = "en",
) -> tuple[dict | None, object | None]:
    """Return (audit_dict, llm_call). ``(None, None)`` when skipped or on error."""
    if not rewritten or provider.model.startswith("mock") or not audit_enabled():
        return None, None
    must = "\n".join(f"- {m}" for m in (must_fix or [])) or "- (none)"
    user = (
        f"【原始文案】\n<<<ORIGINAL\n{original}\nORIGINAL\n\n"
        f"【必须修复清单】\n{must}\n\n"
        f"【改写后文案】\n<<<REVISED\n{rewritten}\nREVISED"
    )
    try:
        call = provider.chat(_AUDIT_SYSTEM, user, json_mode=True)
        data = json.loads(call.text)
    except (LLMError, json.JSONDecodeError, ValueError):
        return None, None
    results = data.get("audit_results") or {}
    if not isinstance(results, dict):
        results = {}
    return (
        {
            "status": str(data.get("status", "")).upper(),
            "audit_results": results,
            "audit_notes": str(data.get("audit_notes", "")),
            "issues": list(data.get("issues") or []),
        },
        call,
    )
