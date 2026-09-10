"""Queue dispatch tests: Celery eager mode must run jobs to completion."""
from __future__ import annotations

import os

from tests.conftest import _auth, build_pptx, register_verified

PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def test_celery_eager_generation(client):
    os.environ["TASK_BACKEND"] = "celery"
    os.environ["CELERY_EAGER"] = "true"
    os.environ["EXEC_ASYNC"] = "true"
    try:
        token, _ = register_verified(client)
        client.post(
            "/api/billing/topup", headers=_auth(token),
            json={"amount": 10, "currency": "USD"},
        )
        name, data = build_pptx(2)
        up = client.post(
            "/api/projects", headers=_auth(token),
            files={"file": (name, data, PPTX_MIME)},
        )
        pid = up.json()["id"]

        r = client.post(f"/api/projects/{pid}/generate", headers=_auth(token))
        assert r.status_code == 200, r.text

        jobs = client.get(f"/api/projects/{pid}/jobs", headers=_auth(token)).json()
        assert jobs[0]["status"] == "succeeded", jobs[0]

        detail = client.get(f"/api/projects/{pid}", headers=_auth(token)).json()
        assert all(p["note_text"] for p in detail["pages"])
    finally:
        os.environ["TASK_BACKEND"] = "thread"
        os.environ["CELERY_EAGER"] = "false"
        os.environ["EXEC_ASYNC"] = "false"
