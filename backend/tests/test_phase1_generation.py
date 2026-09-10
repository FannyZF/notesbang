"""Phase 1 MVP pipeline integration tests (mock LLM provider)."""
from __future__ import annotations

from app.core.counters import count_chars
from tests.conftest import _auth, build_pptx, register_verified

PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def _upload(client, token, name, data, mime=PPTX_MIME):
    return client.post(
        "/api/projects",
        headers=_auth(token),
        files={"file": (name, data, mime)},
    )


def _project_with_pages(client, token, n=2):
    name, data = build_pptx(n)
    up = _upload(client, token, name, data)
    assert up.status_code == 201, up.text
    return up.json()


def test_plan_allocates_targets(client):
    token, _ = register_verified(client)
    project = _project_with_pages(client, token, 2)
    r = client.post(
        f"/api/projects/{project['id']}/plan", headers=_auth(token)
    )
    assert r.status_code == 200, r.text
    plan = r.json()
    assert len(plan["pages"]) == 2
    assert plan["total_units"] > 0
    got = sum(p["target_chars"] for p in plan["pages"])
    assert abs(got - plan["total_units"]) <= len(plan["pages"]) * 2


def test_trial_whole_generate_marks_used_and_limits(client):
    token, _ = register_verified(client)
    project = _project_with_pages(client, token, 2)
    pid = project["id"]

    first = client.post(f"/api/projects/{pid}/generate", headers=_auth(token))
    assert first.status_code == 200, first.text
    assert first.json()["updated_pages"] == 2
    assert first.json()["charged_points"] == 0

    got = client.get(f"/api/projects/{pid}", headers=_auth(token)).json()
    for page in got["pages"]:
        assert page["note_text"]
        assert page["status"] == "generated"

    ent = client.get("/api/billing/entitlements", headers=_auth(token)).json()
    assert ent["trial_used"] is True
    assert ent["export_locked"] is True  # still locked until top-up

    # One free whole regeneration remains in the trial budget.
    second = client.post(f"/api/projects/{pid}/generate", headers=_auth(token))
    assert second.status_code == 200

    # Third whole regeneration must ask for funds.
    third = client.post(f"/api/projects/{pid}/generate", headers=_auth(token))
    assert third.status_code == 402
    assert third.headers.get("X-Error-Code") == "TRIAL_LIMIT_REACHED"


def test_notes_length_within_tolerance(client):
    token, _ = register_verified(client)
    project = _project_with_pages(client, token, 2)
    pid = project["id"]
    client.put(
        f"/api/projects/{pid}/settings",
        headers=_auth(token),
        json={"target_minutes": 10},
    )
    plan = client.post(f"/api/projects/{pid}/plan", headers=_auth(token)).json()
    r = client.post(f"/api/projects/{pid}/generate", headers=_auth(token))
    assert r.status_code == 200, r.text
    got = client.get(f"/api/projects/{pid}", headers=_auth(token)).json()
    targets = {p["ord"]: p["target_chars"] for p in plan["pages"]}
    for page in got["pages"]:
        t = targets[page["ord"]]
        c = count_chars(page["note_text"])
        assert abs(c - t) <= t * 0.15 + 1, (page["ord"], c, t)


def test_paid_whole_generation_charges_and_page_regen(client):
    token, _ = register_verified(client)
    tp = client.post(
        "/api/billing/topup", headers=_auth(token),
        json={"amount": 20, "currency": "USD"},
    )
    assert tp.status_code == 200

    project = _project_with_pages(client, token, 3)
    pid = project["id"]

    gen = client.post(f"/api/projects/{pid}/generate", headers=_auth(token))
    assert gen.status_code == 200, gen.text
    assert gen.json()["charged_points"] == 3

    wallet = client.get("/api/billing/wallet", headers=_auth(token)).json()
    assert wallet["balance"] == 17

    page_id = project["pages"][0]["id"]
    regen = client.post(
        f"/api/projects/{pid}/pages/{page_id}/regenerate", headers=_auth(token)
    )
    assert regen.status_code == 200, regen.text
    assert regen.json()["charged_points"] == 1
    wallet2 = client.get("/api/billing/wallet", headers=_auth(token)).json()
    assert wallet2["balance"] == 16


def test_insufficient_balance_rejected_before_generation(client):
    token, _ = register_verified(client)
    project = _project_with_pages(client, token, 2)
    pid = project["id"]
    # Consume trial budget by generating.
    assert client.post(f"/api/projects/{pid}/generate", headers=_auth(token)).status_code == 200
    # Top up 1 point only: 2-page whole generation costs 2 -> rejected.
    client.post(
        "/api/billing/topup", headers=_auth(token),
        json={"amount": 1, "currency": "USD"},
    )
    r = client.post(f"/api/projects/{pid}/generate", headers=_auth(token))
    assert r.status_code == 402
    assert r.headers.get("X-Error-Code") == "INSUFFICIENT_BALANCE"


def test_cue_mode_and_style_settings(client):
    token, _ = register_verified(client)
    project = _project_with_pages(client, token, 2)
    pid = project["id"]
    bad = client.put(
        f"/api/projects/{pid}/settings",
        headers=_auth(token),
        json={"style": "not_a_style"},
    )
    assert bad.status_code == 422
    assert bad.headers.get("X-Error-Code") == "UNKNOWN_STYLE"

    ok = client.put(
        f"/api/projects/{pid}/settings",
        headers=_auth(token),
        json={
            "note_mode": "cue",
            "style": "academic",
            "custom_scenario": "Present results at a research conference",
            "output_lang": "zh",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["note_mode"] == "cue"


def test_speech_measurement_updates_speed(client):
    token, _ = register_verified(client)
    sample = client.get("/api/speech/sample", headers=_auth(token)).json()
    assert sample["chars"] > 50
    r = client.post(
        "/api/speech/measure",
        headers=_auth(token),
        json={"duration_ms": 60_000},
    )
    assert r.status_code == 200
    cps = r.json()["cps"]
    assert cps > 0
    # Setting manual speed then reading it back via plan.
    project = _project_with_pages(client, token, 2)
    client.put(
        f"/api/projects/{project['id']}/settings",
        headers=_auth(token),
        json={"speed_source": "manual", "speed_cps": 4.0},
    )
    plan = client.post(
        f"/api/projects/{project['id']}/plan", headers=_auth(token)
    ).json()
    assert plan["speed_cps"] == 4.0
