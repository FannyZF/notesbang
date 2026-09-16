"""Corpus flywheel: outcome labels + admin corpus stats/export."""
from __future__ import annotations

import os

from tests.conftest import _auth, register_verified

SAMPLE = "我用3个月把粉丝从0做到1万，方法只有3步。你最常用哪一招？评论区告诉我。"


def test_outcome_and_admin_corpus(client):
    os.environ["ADMIN_TOKEN"] = "test-admin-token"
    try:
        token, _ = register_verified(client)
        doc = client.post(
            "/api/documents",
            headers=_auth(token),
            json={"title": "增长", "content": SAMPLE, "platform": "xiaohongshu"},
        ).json()
        client.post(f"/api/documents/{doc['id']}/analyze", headers=_auth(token))
        out = client.post(
            f"/api/documents/{doc['id']}/outcome",
            headers=_auth(token),
            json={"reads": 12000, "likes": 900, "saves": 300},
        )
        assert out.status_code == 200

        stats = client.get(
            "/api/admin/corpus/stats",
            headers={"Authorization": "Bearer test-admin-token"},
        ).json()
        assert stats["documents"] >= 1
        assert stats["corpus_features"] >= 1
        assert stats["outcome_ready"] >= 1
        assert "hook" in stats["dimension_avg_score"]

        export = client.get(
            "/api/admin/corpus/export",
            headers={"Authorization": "Bearer test-admin-token"},
        )
        assert export.status_code == 200
        assert b"xiaohongshu" in export.content
        assert b"reads" in export.content  # outcome included
    finally:
        os.environ.pop("ADMIN_TOKEN", None)
