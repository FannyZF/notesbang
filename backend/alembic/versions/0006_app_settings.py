"""app_settings (runtime admin overrides)

Revision ID: 0006_app_settings
Revises: 0005_job_params
Create Date: 2026-09-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_app_settings"
down_revision = "0005_job_params"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "app_settings" not in tables:
        op.create_table(
            "app_settings",
            sa.Column("key", sa.String(64), primary_key=True),
            sa.Column("value", sa.Text(), nullable=False, server_default=""),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "app_settings" in tables:
        op.drop_table("app_settings")
