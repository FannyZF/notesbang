"""SQLAlchemy engine/session setup.

Phase 0 runs with the default SQLite URL for a zero-infra local experience and
uses ``create_all`` on startup (Alembic migrations arrive in Phase 1, per PRD
§15 engineering foundations).
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()
_connect_args = {"check_same_thread": False} if _settings.is_sqlite else {}
engine = create_engine(
    _settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
)


if _settings.is_sqlite:
    # Allow the async worker thread to write while request threads read.
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=15000")
        cursor.close()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _sql_type(col) -> str:
    name = str(col.type).upper()
    if name.startswith("BOOL"):
        return "INTEGER"
    if name.startswith("INT") or name.startswith("BIGINT"):
        return "INTEGER"
    if name.startswith("FLOAT") or name.startswith("DOUBLE"):
        return "FLOAT"
    if name.startswith("DATETIME") or name.startswith("TIMESTAMP"):
        return "DATETIME"
    return "TEXT"


def ensure_schema() -> None:
    """Lightweight additive migration for SQLite (create_all adds tables only).

    New columns added to existing tables after first deploy are back-filled with
    sensible defaults so local/dev databases keep working.
    """
    if not _settings.is_sqlite:
        return
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        existing_cols = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name in existing_cols:
                continue
            dflt = ""
            if not col.nullable:
                if isinstance(col.type.python_type, int):
                    dflt = " DEFAULT 0"
                elif isinstance(col.type.python_type, str):
                    dflt = " DEFAULT ''"
            ddl = (
                f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" '
                f"{_sql_type(col)}{dflt}"
            )
            with engine.begin() as conn:
                conn.execute(text(ddl))
            existing_cols.add(col.name)

    # Back-fill NULLs introduced by additive columns.
    backfills = {
        "projects": {
            "note_mode": "script",
            "style": "business",
            "custom_scenario": "",
            "audience": "General",
            "persona": "I",
            "output_lang": "auto",
            "transitions": 1,
            "data_fidelity": 1,
            "speed_source": "default",
            "quality_mode": "full",
            "vision_enabled": 1,
        },
        "pages": {"note_mode": "script", "status": "parsed", "weight": 1.0},
        "jobs": {"phase": ""},
    }
    for table_name, columns in backfills.items():
        if not insp.has_table(table_name):
            continue
        existing = {c["name"] for c in insp.get_columns(table_name)}
        with engine.begin() as conn:
            for col, value in columns.items():
                if col in existing:
                    conn.execute(
                        text(
                            f'UPDATE "{table_name}" SET "{col}" = :v '
                            f'WHERE "{col}" IS NULL'
                        ),
                        {"v": value},
                    )

    # Normalise legacy localized option values to canonical codes.
    value_fixes = {
        "projects": {
            "output_lang": {"跟随": "auto", "中文": "zh", "英文": "en"},
        }
    }
    for table_name, columns in value_fixes.items():
        if not insp.has_table(table_name):
            continue
        existing = {c["name"] for c in insp.get_columns(table_name)}
        with engine.begin() as conn:
            for col, mapping in columns.items():
                if col not in existing:
                    continue
                for old, new in mapping.items():
                    conn.execute(
                        text(
                            f'UPDATE "{table_name}" SET "{col}" = :new '
                            f'WHERE "{col}" = :old'
                        ),
                        {"new": new, "old": old},
                    )


def _utcnow():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


def reset_stale_jobs(older_than_seconds: int = 3600) -> int:
    """Mark jobs that survived a process restart as failed.

    A crashed/restarted worker leaves rows in queued/running forever, which made
    clients time out polling them. Called on startup (see init_db).
    """
    from app.models import Job

    cutoff = _utcnow()
    stale = 0
    with SessionLocal() as session:
        rows = (
            session.query(Job)
            .filter(Job.status.in_(["queued", "running"]))
            .all()
        )
        for job in rows:
            created = job.created_at
            if created is not None and created.tzinfo is None:
                created = created.replace(tzinfo=cutoff.tzinfo)
            if created is None or (cutoff - created).total_seconds() > older_than_seconds:
                job.status = "failed"
                job.phase = "Interrupted (server restarted)"
                job.error = "STALE_JOB_RESET"
                stale += 1
        session.commit()
    return stale


def init_db() -> None:
    # Import models so they register on Base.metadata before create_all.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ensure_schema()
    reset_stale_jobs()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
