"""Phase 2 structure / page-edit / review / PDF-export tests."""
from __future__ import annotations

from app.db.base import SessionLocal
from app.models import PageRevision
from tests.conftest import _auth, build_pptx, register_verified

PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def _paid_generated(client, n=2):
    token, _ = register_verified(client)
    client.post(
        "/api/billing/topup", headers=_auth(token),
        json={"amount": 20, "currency": "USD"},
    )
    name, data = build_pptx(n)
    up = client.post(
        "/api/projects", headers=_auth(token),
        files={"file": (name, data, PPTX_MIME)},
    )
    pid = up.json()["id"]
    assert client.post(f"/api/projects/{pid}/generate", headers=_auth(token)).status_code == 200
    detail = client.get(f"/api/projects/{pid}", headers=_auth(token)).json()
    return token, pid, detail


def test_page_edit_backup_and_version_conflict(client):
    token, pid, detail = _paid_generated(client, 1)
    page = detail["pages"][0]
    v0 = page["version"]

    upd = client.put(
        f"/api/projects/{pid}/pages/{page['id']}",
        headers=_auth(token),
        json={"note_text": "用户改写后的讲稿内容。", "expected_version": v0},
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["note_text"] == "用户改写后的讲稿内容。"
    assert upd.json()["version"] == v0 + 1

    # Stale version must be rejected.
    stale = client.put(
        f"/api/projects/{pid}/pages/{page['id']}",
        headers=_auth(token),
        json={"note_text": "旧版本改写。", "expected_version": v0},
    )
    assert stale.status_code == 409
    assert stale.headers.get("X-Error-Code") == "REVISION_CONFLICT"

    db = SessionLocal()
    try:
        backups = db.query(PageRevision).filter(PageRevision.page_id == page["id"]).all()
        assert len(backups) == 1
        assert backups[0].note_text == detail["pages"][0]["note_text"]
    finally:
        db.close()


def test_structure_save_and_validation(client):
    token, pid, detail = _paid_generated(client, 3)
    pages = detail["pages"]  # ord 1..3
    ids = {p["id"]: p["ord"] for p in pages}
    by_ord = {p["ord"]: p["id"] for p in pages}

    payload = {
        "sections": [
            {
                "name": "开场与背景",
                "pages": [
                    {"page_id": by_ord[1], "ord": 1, "weight": 2.0},
                    {"page_id": by_ord[2], "ord": 2, "weight": 1.0},
                ],
            },
            {
                "name": "总结",
                "pages": [{"page_id": by_ord[3], "ord": 3, "weight": 1.0}],
            },
        ]
    }
    r = client.put(
        f"/api/projects/{pid}/structure", headers=_auth(token), json=payload
    )
    assert r.status_code == 200, r.text
    after = r.json()
    w = {p["ord"]: p["weight"] for p in after["pages"]}
    assert w[1] == 2.0

    # Dropping a page must be rejected.
    bad = {
        "sections": [
            {"name": "只有一页", "pages": [{"page_id": by_ord[1], "ord": 1, "weight": 1.0}]}
        ]
    }
    b = client.put(
        f"/api/projects/{pid}/structure", headers=_auth(token), json=bad
    )
    assert b.status_code == 422
    assert b.headers.get("X-Error-Code") == "INVALID_STRUCTURE"


def test_review_flags_duplicate_openings(client):
    token, pid, _ = _paid_generated(client, 2)
    r = client.post(f"/api/projects/{pid}/review", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["clean"] is False
    assert any(i["severity"] == "warn" for i in body["issues"])


def test_pdf_export(client):
    token, pid, _ = _paid_generated(client, 2)
    r = client.post(
        f"/api/projects/{pid}/export",
        headers=_auth(token),
        params={"fmt": "pdf"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_structure_get_after_save(client):
    token, pid, detail = _paid_generated(client, 3)
    by_ord = {p["ord"]: p["id"] for p in detail["pages"]}
    payload = {
        "sections": [
            {"name": "背景", "pages": [{"page_id": by_ord[1], "ord": 1, "weight": 1.0}]},
            {
                "name": "方案",
                "pages": [
                    {"page_id": by_ord[2], "ord": 1, "weight": 1.0},
                    {"page_id": by_ord[3], "ord": 2, "weight": 1.0},
                ],
            },
        ]
    }
    assert client.put(
        f"/api/projects/{pid}/structure", headers=_auth(token), json=payload
    ).status_code == 200
    got = client.get(f"/api/projects/{pid}/structure", headers=_auth(token)).json()
    assert len(got["sections"]) == 2
    names = [s["name"] for s in got["sections"]]
    assert names == ["背景", "方案"]
    assert sorted(got["sections"][1]["pages"]) == [by_ord[2], by_ord[3]]


def test_change_password_and_resend_verification(client):
    token, _ = register_verified(client)
    # Wrong current password rejected.
    bad = client.post(
        "/api/auth/change-password",
        headers=_auth(token),
        json={"current": "nope", "new": "newpass123"},
    )
    assert bad.status_code == 400
    assert bad.headers.get("X-Error-Code") == "WRONG_PASSWORD"
    ok = client.post(
        "/api/auth/change-password",
        headers=_auth(token),
        json={"current": "phase0secret", "new": "newpass123"},
    )
    assert ok.status_code == 200
    # Old password no longer works.
    old_login = client.post(
        "/api/auth/login", json={"email": _me_email(client, token), "password": "phase0secret"}
    )
    assert old_login.status_code == 401
    # Verified user: resend reports already verified.
    resend = client.post("/api/auth/resend-verification", headers=_auth(token))
    assert resend.status_code == 200
    assert resend.json()["already_verified"] is True


def _me_email(client, token):
    return client.get("/api/auth/me", headers=_auth(token)).json()["email"]


def test_delete_project_removes_record(client):
    token, pid, _ = _paid_generated(client, 2)
    d = client.delete(f"/api/projects/{pid}", headers=_auth(token))
    assert d.status_code == 200
    assert d.json()["deleted_project_id"] == pid
    gone = client.get(f"/api/projects/{pid}", headers=_auth(token))
    assert gone.status_code == 404
    listed = client.get("/api/projects", headers=_auth(token)).json()
    assert all(x["id"] != pid for x in listed)


def test_emphasis_limited_to_twenty_percent(client):
    token, pid, detail = _paid_generated(client, 6)
    page_ids = [p["id"] for p in detail["pages"]]

    def set_emph(page_id, on):
        return client.put(
            f"/api/projects/{pid}/pages/{page_id}",
            headers=_auth(token),
            json={"weight": 1.6 if on else 1.0, "expected_version": _ver(client, token, pid, page_id)},
        )

    assert set_emph(page_ids[0], True).status_code == 200
    assert set_emph(page_ids[1], True).status_code == 200
    # ceil(6*0.2)=2 emphasized max -> third must be rejected.
    blocked = set_emph(page_ids[2], True)
    assert blocked.status_code == 422
    assert blocked.headers.get("X-Error-Code") == "EMPHASIS_LIMIT"
    # Removing emphasis frees a slot.
    assert set_emph(page_ids[0], False).status_code == 200
    assert set_emph(page_ids[2], True).status_code == 200


def test_revision_list_and_restore(client):
    token, pid, detail = _paid_generated(client, 1)
    page = detail["pages"][0]
    pid_page = page["id"]
    v = page["version"]

    def put(text):
        nonlocal v
        r = client.put(
            f"/api/projects/{pid}/pages/{pid_page}",
            headers=_auth(token),
            json={"note_text": text, "expected_version": v},
        )
        assert r.status_code == 200, r.text
        v = r.json()["version"]

    put("first manual edit")
    put("second manual edit")

    revs = client.get(
        f"/api/projects/{pid}/pages/{pid_page}/revisions", headers=_auth(token)
    ).json()
    assert len(revs) >= 2
    # Restore the earliest recorded revision.
    earliest = revs[-1]
    restore = client.put(
        f"/api/projects/{pid}/pages/{pid_page}/restore",
        headers=_auth(token),
        json={"revision_id": earliest["id"]},
    )
    assert restore.status_code == 200, restore.text
    assert restore.json()["note_text"] == earliest["note_text"]


def _ver(client, token, pid, page_id):
    p = client.get(f"/api/projects/{pid}", headers=_auth(token)).json()
    for pg in p["pages"]:
        if pg["id"] == page_id:
            return pg["version"]
    raise AssertionError("page not found")
