"""Async job execution (Phase 2): generate returns queued; client polls jobs."""
from __future__ import annotations

import os
import time

from tests.conftest import _auth, build_pptx, register_verified

PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def test_async_generate_queued_then_succeeds(client):
    os.environ["EXEC_ASYNC"] = "true"
    try:
        token, _ = register_verified(client)
        client.post(
            "/api/billing/topup", headers=_auth(token),
            json={"amount": 10, "currency": "USD"},
        )
        name, data = build_pptx(2)
        up = client.post(
            "/api/projects",
            headers=_auth(token),
            files={"file": (name, data, PPTX_MIME)},
        )
        pid = up.json()["id"]

        r = client.post(f"/api/projects/{pid}/generate", headers=_auth(token))
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "queued"

        job = _wait_job(client, token, pid)
        assert job["status"] == "succeeded", job
        assert job["type"] == "generate_whole"

        detail = client.get(f"/api/projects/{pid}", headers=_auth(token)).json()
        assert all(p["status"] == "generated" and p["note_text"] for p in detail["pages"])

        wallet = client.get("/api/billing/wallet", headers=_auth(token)).json()
        assert wallet["balance"] == 8  # 2 pages x 1 point charged after success
    finally:
        os.environ["EXEC_ASYNC"] = "false"


def test_async_page_regenerate(client):
    os.environ["EXEC_ASYNC"] = "true"
    try:
        token, _ = register_verified(client)
        client.post(
            "/api/billing/topup", headers=_auth(token),
            json={"amount": 10, "currency": "USD"},
        )
        name, data = build_pptx(2)
        up = client.post(
            "/api/projects",
            headers=_auth(token),
            files={"file": (name, data, PPTX_MIME)},
        )
        pid = up.json()["id"]
        page = up.json()["pages"][0]

        assert (
            client.post(f"/api/projects/{pid}/generate", headers=_auth(token)).status_code
            == 200
        )
        _wait_job(client, token, pid)

        rr = client.post(
            f"/api/projects/{pid}/pages/{page['id']}/regenerate", headers=_auth(token)
        )
        assert rr.status_code == 200
        assert rr.json()["status"] == "queued"
        job = _wait_job(client, token, pid, kind="generate_page")
        assert job["status"] == "succeeded"
    finally:
        os.environ["EXEC_ASYNC"] = "false"


def _wait_job(client, token, pid, kind=None, timeout=15.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        jobs = client.get(f"/api/projects/{pid}/jobs", headers=_auth(token)).json()
        if jobs:
            latest = jobs[0]
            if kind is None or latest["type"] == kind:
                if latest["status"] == "failed":
                    raise AssertionError(f"job failed early: {latest}")
                if latest["status"] in ("succeeded", "failed"):
                    return latest
        time.sleep(0.15)
    raise AssertionError("job did not finish in time")
