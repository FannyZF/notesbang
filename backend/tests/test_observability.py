"""Observability: request id header + Prometheus metrics endpoint."""
from __future__ import annotations


def test_request_id_and_metrics(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.headers.get("X-Request-ID")

    m = client.get("/metrics")
    assert m.status_code == 200
    body = m.text
    assert "notesbang_http_requests_total" in body
