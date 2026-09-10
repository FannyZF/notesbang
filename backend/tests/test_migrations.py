"""Alembic baseline migration smoke test (runs on a temp SQLite file)."""
from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_head(tmp_path: Path, monkeypatch):
    db_file = tmp_path / "mig.db"
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", f"sqlite:///{db_file}")
    cfg = Config(str(Path("alembic.ini").resolve()))
    command.upgrade(cfg, "head")

    engine = create_engine(f"sqlite:///{db_file}")
    tables = set(inspect(engine).get_table_names())
    assert {"users", "projects", "pages", "jobs", "wallets", "ledger_entries"} <= tables
    assert "alembic_version" in tables

    # Idempotent re-run.
    command.upgrade(cfg, "head")

    command.downgrade(cfg, "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]
