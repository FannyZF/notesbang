"""Review-committee tests: expert rows, spread, consensus, job lifecycle."""
from __future__ import annotations

from app.db.base import SessionLocal
from app.models import Analysis, DimensionScore, ExpertScore, Job
from tests.conftest import _auth, register_verified

SAMPLE = "我用3个月把粉丝从0做到1万，方法只有3步。你最常用哪一招？评论区告诉我。"


def _doc(client, token):
    return client.post(
        "/api/documents",
        headers=_auth(token),
        json={"title": "增长", "content": SAMPLE, "platform": "xiaohongshu"},
    ).json()


def _run(client, token, doc_id):
    start = client.post(
        f"/api/documents/{doc_id}/analyze?lang=zh", headers=_auth(token)
    ).json()
    job = client.get(f"/api/jobs/{start['job_id']}", headers=_auth(token)).json()
    assert job["status"] == "succeeded", job
    return start["job_id"], client.get(
        f"/api/documents/{doc_id}/analysis?lang=zh", headers=_auth(token)
    ).json()


def test_job_lifecycle_and_ownership(client):
    token, _ = register_verified(client)
    doc = _doc(client, token)
    job_id, _card = _run(client, token, doc["id"])

    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        assert job.type == "analyze"
        assert job.document_id == doc["id"]
        assert job.phase in ("Done", "Finalizing")
        assert job.progress == 100
    finally:
        db.close()

    # Another user cannot read the job.
    other, _ = register_verified(client)
    assert client.get(f"/api/jobs/{job_id}", headers=_auth(other)).status_code == 404
    assert client.get("/api/jobs/999999", headers=_auth(token)).status_code == 404


def test_expert_rows_and_aggregates(client):
    token, _ = register_verified(client)
    doc = _doc(client, token)
    _, card = _run(client, token, doc["id"])

    assert len(card["experts"]) == 5
    assert {e["key"] for e in card["experts"]} == {
        "compliance",
        "viral",
        "sme",
        "audience",
        "structure",
    }
    for d in card["dimensions"]:
        assert len(d["viewpoints"]) == 5
        assert d["spread"] == 0  # mock: all experts agree

    db = SessionLocal()
    try:
        analysis = db.get(Analysis, card["id"])
        rows = (
            db.query(ExpertScore)
            .filter(ExpertScore.analysis_id == analysis.id)
            .all()
        )
        assert len(rows) == 5 * 7  # five experts x seven dimensions
        dims = (
            db.query(DimensionScore)
            .filter(DimensionScore.analysis_id == analysis.id)
            .all()
        )
        assert len(dims) == 7
    finally:
        db.close()


def test_committee_is_deterministic(client):
    token, _ = register_verified(client)
    d1 = _doc(client, token)
    d2 = _doc(client, token)
    _, c1 = _run(client, token, d1["id"])
    _, c2 = _run(client, token, d2["id"])
    assert c1["overall_score"] == c2["overall_score"]
    assert [d["score"] for d in c1["dimensions"]] == [d["score"] for d in c2["dimensions"]]
