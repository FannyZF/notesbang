"""Prometheus metrics (optional; degrades to no-ops if not installed)."""
from __future__ import annotations

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Histogram,
        generate_latest,
    )

    _OK = True
    HTTP_REQUESTS = Counter(
        "notesbang_http_requests_total", "HTTP requests", ["method", "path", "status"]
    )
    HTTP_LATENCY = Histogram(
        "notesbang_http_request_seconds", "HTTP latency", ["method", "path"]
    )
    GENERATIONS = Counter(
        "notesbang_generations_total", "Generation jobs", ["status"]
    )
    GENERATED_PAGES = Counter(
        "notesbang_generated_pages_total", "Pages generated"
    )
    LLM_COST = Counter("notesbang_llm_cost_usd_total", "Estimated LLM cost (USD)")
except Exception:  # pragma: no cover
    _OK = False

    class _Noop:
        def labels(self, *a, **k):
            return self

        def inc(self, *a, **k):
            return None

        def observe(self, *a, **k):
            return None

    HTTP_REQUESTS = HTTP_LATENCY = GENERATIONS = GENERATED_PAGES = LLM_COST = _Noop()


def render_metrics() -> tuple[bytes, str]:
    if not _OK:
        return b"", "text/plain"
    return generate_latest(), CONTENT_TYPE_LATEST
