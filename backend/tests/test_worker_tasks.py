"""Celery task registration guards.

The worker runs with ``-A app.workers.celery_app:celery_app``; if a task name
sent by ``runner.run_job`` is not registered, Celery silently discards it and
the job stays "queued" forever. These tests pin that contract.
"""
from __future__ import annotations


def test_analysis_task_is_registered():
    from app.workers import celery_tasks  # noqa: F401  (registers tasks)
    from app.workers.celery_app import celery_app
    from app.workers.jobs import run_analysis_task

    expected = f"jobs.{run_analysis_task.__name__}"
    assert expected == "jobs.run_analysis_task"
    assert expected in celery_app.tasks
    assert "jobs.retention_cleanup" in celery_app.tasks


def test_run_job_rejects_unregistered_task():
    import pytest

    from app.workers import runner

    def not_a_task(db, job):  # pragma: no cover - never executed
        raise AssertionError

    monkey = pytest.MonkeyPatch()
    monkey.setenv("TASK_BACKEND", "celery")
    try:
        with pytest.raises(RuntimeError, match="not registered"):
            runner.run_job(1, not_a_task)
    finally:
        monkey.undo()
