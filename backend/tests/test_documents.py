"""Content-scoring API tests (mock provider = deterministic)."""
from __future__ import annotations

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


def test_platforms_list(client):
    token, _ = register_verified(client)
    r = client.get("/api/documents/platforms?lang=zh", headers=_auth(token))
    assert r.status_code == 200
    keys = {p["key"] for p in r.json()}
    assert {"xiaohongshu", "wechat", "linkedin", "x", "blog"} <= keys


def test_create_analyze_scorecard(client):
    token, _ = register_verified(client)
    doc = _new_doc(client, token)
    assert doc["char_count"] > 0
    assert doc["language"] == "zh"

    r = client.post(f"/api/documents/{doc['id']}/analyze", headers=_auth(token))
    assert r.status_code == 200, r.text
    card = r.json()
    assert card["overall_score"] == 50  # mock: all bands 3, midpoint 50
    assert len(card["dimensions"]) == 6
    for d in card["dimensions"]:
        assert d["band"] == 3 and d["score"] == 50
        assert d["evidence"] and d["evidence"][0]["verified"] is True
        assert d["suggestions"]

    again = client.get(f"/api/documents/{doc['id']}/analysis", headers=_auth(token))
    assert again.status_code == 200
    assert again.json()["overall_score"] == 50


def test_focus_boosts_dimension_weight(client):
    token, _ = register_verified(client)
    doc = _new_doc(client, token)
    base = client.post(
        f"/api/documents/{doc['id']}/analyze", headers=_auth(token)
    ).json()
    weights = {d["key"]: d["weight"] for d in base["dimensions"]}
    focused = client.post(
        f"/api/documents/{doc['id']}/analyze?focus=hook,title", headers=_auth(token)
    ).json()
    fw = {d["key"]: d["weight"] for d in focused["dimensions"]}
    assert fw["hook"] > weights["hook"]
    assert fw["title"] > weights["title"]
    assert abs(sum(fw.values()) - 1.0) < 0.01


def test_rewrite_full_titles_hooks_and_export(client):
    token, _ = register_verified(client)
    doc = _new_doc(client, token)
    client.post(f"/api/documents/{doc['id']}/analyze", headers=_auth(token))

    full = client.post(
        f"/api/documents/{doc['id']}/rewrite", headers=_auth(token), json={"kind": "full"}
    )
    assert full.status_code == 200 and full.json()["content"]
    assert "diff" in full.json()["meta"]

    titles = client.post(
        f"/api/documents/{doc['id']}/rewrite", headers=_auth(token), json={"kind": "title"}
    )
    assert titles.status_code == 200
    assert len(__import__("json").loads(titles.json()["content"])) == 5

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
    for _ in range(5):
        doc = _new_doc(client, token)
        assert client.post(
            f"/api/documents/{doc['id']}/analyze", headers=_auth(token)
        ).status_code == 200
    sixth = _new_doc(client, token)
    blocked = client.post(f"/api/documents/{sixth['id']}/analyze", headers=_auth(token))
    assert blocked.status_code == 429
    assert blocked.headers.get("X-Error-Code") == "DAILY_LIMIT_REACHED"


def test_char_cap(client):
    token, _ = register_verified(client)
    r = client.post(
        "/api/documents",
        headers=_auth(token),
        json={"title": "too long", "content": "字" * 3001},
    )
    assert r.status_code == 422
    assert r.headers.get("X-Error-Code") == "CONTENT_TOO_LONG"


def test_upload_txt(client):
    token, _ = register_verified(client)
    r = client.post(
        "/api/documents/upload?platform=blog",
        headers=_auth(token),
        files={"file": ("post.md", SAMPLE.encode("utf-8"), "text/markdown")},
    )
    assert r.status_code == 201, r.text
    assert r.json()["source_format"] == "md"
