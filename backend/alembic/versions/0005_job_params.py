"""jobs.params_json (focus/lang for async analyses)

Revision ID: 0005_job_params
Revises: 0004_committee
Create Date: 2026-09-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_job_params"
down_revision = "0004_committee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("jobs")}
    if "params_json" not in cols:
        with op.batch_alter_table("jobs") as batch:
            batch.add_column(
                sa.Column("params_json", sa.Text(), nullable=False, server_default="{}")
            )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("jobs")}
    if "params_json" in cols:
        with op.batch_alter_table("jobs") as batch:
            batch.drop_column("params_json")
