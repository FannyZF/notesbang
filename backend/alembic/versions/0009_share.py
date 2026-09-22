"""shares (public read-only scorecard links)

Revision ID: 0009_share
Revises: 0008_document_archetype
Create Date: 2026-09-21
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_share"
down_revision = "0008_document_archetype"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "shares" in tables:
        return
    op.create_table(
        "shares",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token_digest", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("analysis_id", sa.Integer(), sa.ForeignKey("analyses.id"), nullable=False),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("include_content", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_shares_token_digest", "shares", ["token_digest"], unique=True)
    op.create_index("ix_shares_user_id", "shares", ["user_id"])
    op.create_index("ix_shares_analysis_id", "shares", ["analysis_id"])
    op.create_index("ix_shares_document_id", "shares", ["document_id"])


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "shares" in tables:
        op.drop_table("shares")
