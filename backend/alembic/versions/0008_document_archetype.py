"""documents.archetype (content archetype axis)

Revision ID: 0008_document_archetype
Revises: 0007_page_views
Create Date: 2026-09-21
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_document_archetype"
down_revision = "0007_page_views"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("documents")}
    if "archetype" not in cols:
        with op.batch_alter_table("documents") as batch:
            batch.add_column(
                sa.Column(
                    "archetype",
                    sa.String(32),
                    nullable=False,
                    server_default="auto",
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("documents")}
    if "archetype" in cols:
        with op.batch_alter_table("documents") as batch:
            batch.drop_column("archetype")
