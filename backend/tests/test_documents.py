"""Content-scoring API tests (mock provider = deterministic).

Analyze is now async: POST returns a job; with EXEC_ASYNC=false the job runs
inline so we can read the analysis immediately (tests also poll the job API).
"""
from __future__ import annotations

import json

from tests.conftest import _auth, register_verified

SAMPLE = (
    "如果你也在为写不出开头发愁，这条能救你。\n\n"
    "我用3个月把粉丝从0做到1万，方法只有3步。\n"
    "第一，先写结论；第二，用具体数字；第三，结尾提问。\n"
    "你最常用哪一招？评论区告诉我。"
)


def _new_doc(client, token, platform="xiaohongshu"):
    r = client.post(
        "/api/documents",
        headers=_auth(token),
        json={"title": "写作技巧", "content": SAMPLE, "platform": platform},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _analyze(client, token, doc_id, focus=""):
    r = client.post(
        f"/api/documents/{doc_id}/analyze?lang=zh&focus={focus}", headers=_auth(token)
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]
    job = client.get(f"/api/jobs/{job_id}", headers=_auth(token)).json()
    assert job["status"] == "succeeded", job
    assert job["document_id"] == doc_id
    return client.get(f"/api/documents/{doc_id}/analysis?lang=zh", headers=_auth(token)).json()


def test_platforms_list(client):
    token, _ = register_verified(client)
    r = client.get("/api/documents/platforms?lang=zh", headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    keys = {p["key"] for p in data["platforms"]}
    assert {"xiaohongshu", "wechat", "linkedin", "x", "blog"} <= keys
    assert data["platforms"][0]["dimensions"]  # dimension labels exposed for focus chips
    assert {a["key"] for a in data["archetypes"]} >= {
        "auto",
        "technical_deep_dive",
        "quick_social_post",
        "industry_case_study",
    }


def test_create_analyze_scorecard(client):
    token, _ = register_verified(client)
    doc = _new_doc(client, token)
    assert doc["char_count"] > 0
    assert doc["language"] == "zh"
    assert doc["archetype"] == "auto"

    card = _analyze(client, token, doc["id"])
    assert card["overall_score"] == 50  # mock committee: all bands 3, midpoint 50
    assert len(card["dimensions"]) == 7
    assert len(card["experts"]) == 5  # five committee members
    for d in card["dimensions"]:
        assert d["band"] == 3 and d["score"] == 50
        assert d["evidence"] and d["evidence"][0]["verified"] is True
        assert d["suggestions"]
        assert len(d["viewpoints"]) == 5  # one viewpoint per expert
        assert "spread" in d
    assert {d["key"] for d in card["dimensions"]} >= {"domain_logic"}
    assert set(card["consensus"].keys()) >= {"top_priorities", "must_fix"}


def test_focus_boosts_dimension_weight(client):
    token, _ = register_verified(client)
    doc = _new_doc(client, token)
    base = _analyze(client, token, doc["id"])
    weights = {d["key"]: d["weight"] for d in base["dimensions"]}
    focused = _analyze(client, token, doc["id"], focus="hook,title")
    fw = {d["key"]: d["weight"] for d in focused["dimensions"]}
    assert fw["hook"] > weights["hook"]
    assert fw["title"] > weights["title"]
    assert abs(sum(fw.values()) - 1.0) < 0.01


def test_rewrite_full_titles_hooks_and_export(client):
    token, _ = register_verified(client)
    doc = _new_doc(client, token)
    _analyze(client, token, doc["id"])

    full = client.post(
        f"/api/documents/{doc['id']}/rewrite",
        headers=_auth(token),
        json={"kind": "full", "adopt": ["compliance", "viral"]},
    )
    assert full.status_code == 200 and full.json()["content"]
    assert "diff" in full.json()["meta"]
    assert full.json()["meta"]["adopt"] == ["compliance", "viral"]

    titles = client.post(
        f"/api/documents/{doc['id']}/rewrite", headers=_auth(token), json={"kind": "title"}
    )
    assert titles.status_code == 200
    assert len(json.loads(titles.json()["content"])) == 5

    hooks = client.post(
        f"/api/documents/{doc['id']}/rewrite", headers=_auth(token), json={"kind": "hook"}
    )
    assert hooks.status_code == 200

    ex = client.get(f"/api/documents/{doc['id']}/export?fmt=md", headers=_auth(token))
    assert ex.status_code == 200
    assert b"Overall score" in ex.content


def test_feedback_and_consent(client):
    token, _ = register_verified(client)
    doc = _new_doc(client, token)
    fb = client.post(
        "/api/documents/feedback",
        headers=_auth(token),
        json={"document_id": doc["id"], "target_type": "analysis", "action": "useful"},
    )
    assert fb.status_code == 200
    c = client.put(
        f"/api/documents/{doc['id']}/consent",
        headers=_auth(token),
        json={"consent_improve": False},
    )
    assert c.json()["consent_improve"] is False


def test_daily_quota(client):
    token, _ = register_verified(client)
    for _ in range(3):
        doc = _new_doc(client, token)
        assert client.post(
            f"/api/documents/{doc['id']}/analyze", headers=_auth(token)
        ).status_code == 200
    fourth = _new_doc(client, token)
    blocked = client.post(f"/api/documents/{fourth['id']}/analyze", headers=_auth(token))
    assert blocked.status_code == 429
    assert blocked.headers.get("X-Error-Code") == "DAILY_LIMIT_REACHED"


def test_quota_endpoint(client):
    token, _ = register_verified(client)
    fresh = client.get("/api/documents/quota", headers=_auth(token)).json()
    assert fresh["remaining"] == fresh["limit"] == 3
    assert fresh["used"] == 0

    doc = _new_doc(client, token)
    assert client.post(
        f"/api/documents/{doc['id']}/analyze", headers=_auth(token)
    ).status_code == 200
    after = client.get("/api/documents/quota", headers=_auth(token)).json()
    assert after["used"] == 1
    assert after["remaining"] == 2


def test_char_cap(client):
    token, _ = register_verified(client)
    r = client.post(
        "/api/documents",
        headers=_auth(token),
        json={"title": "too long", "content": "字" * 3001},
    )
    assert r.status_code == 422
    assert r.headers.get("X-Error-Code") == "CONTENT_TOO_LONG"


def test_delete_document_cascades(client):
    from app.db.base import SessionLocal
    from app.models import Analysis, DimensionScore, ExpertScore, Rewrite

    token, _ = register_verified(client)
    doc = _new_doc(client, token)
    _analyze(client, token, doc["id"])
    client.post(
        f"/api/documents/{doc['id']}/rewrite", headers=_auth(token), json={"kind": "full"}
    )

    d = client.delete(f"/api/documents/{doc['id']}", headers=_auth(token))
    assert d.status_code == 200

    db = SessionLocal()
    try:
        assert db.query(Analysis).filter(Analysis.document_id == doc["id"]).count() == 0
        assert db.query(Rewrite).filter(Rewrite.document_id == doc["id"]).count() == 0
        assert db.query(ExpertScore).count() == 0
        assert db.query(DimensionScore).count() == 0
    finally:
        db.close()

    assert client.get(f"/api/documents/{doc['id']}", headers=_auth(token)).status_code == 404
    assert all(x["id"] != doc["id"] for x in client.get("/api/documents", headers=_auth(token)).json())


def test_upload_txt(client):
    token, _ = register_verified(client)
    r = client.post(
        "/api/documents/upload?platform=blog",
        headers=_auth(token),
        files={"file": ("post.md", SAMPLE.encode("utf-8"), "text/markdown")},
    )
    assert r.status_code == 201, r.text
    assert r.json()["source_format"] == "md"
