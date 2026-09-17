"""review committee: expert scores + spread/consensus + jobs.document_id

Revision ID: 0004_committee
Revises: 0003_drop_speaker_notes
Create Date: 2026-09-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

import app.models  # noqa: F401
from app.db.base import Base

revision = "0004_committee"
down_revision = "0003_drop_speaker_notes"
branch_labels = None
depends_on = None


def _add_column(table: str, column: sa.Column) -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns(table)}
    if column.name not in cols:
        with op.batch_alter_table(table) as batch:
            batch.add_column(column)


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.tables["expert_scores"].create(bind=bind, checkfirst=True)
    _add_column(
        "dimension_scores",
        sa.Column("spread", sa.Float(), nullable=False, server_default="0"),
    )
    _add_column(
        "analyses",
        sa.Column("consensus_json", sa.Text(), nullable=False, server_default="{}"),
    )
    _add_column("jobs", sa.Column("document_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    job_indexes = {i["name"] for i in inspector.get_indexes("jobs")}
    if "ix_jobs_document_id" in job_indexes:
        op.drop_index("ix_jobs_document_id", table_name="jobs")
    for table, col in (
        ("jobs", "document_id"),
        ("analyses", "consensus_json"),
        ("dimension_scores", "spread"),
    ):
        cols = {c["name"] for c in sa.inspect(bind).get_columns(table)}
        if col in cols:
            with op.batch_alter_table(table) as batch:
                batch.drop_column(col)
    Base.metadata.tables["expert_scores"].drop(bind=bind, checkfirst=True)
