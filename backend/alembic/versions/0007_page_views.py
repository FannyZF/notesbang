"""page_views (privacy-friendly traffic stats)

Revision ID: 0007_page_views
Revises: 0006_app_settings
Create Date: 2026-09-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_page_views"
down_revision = "0006_app_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "page_views" in tables:
        return
    op.create_table(
        "page_views",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("day", sa.String(10), nullable=False),
        sa.Column("path", sa.String(200), nullable=False, server_default="/"),
        sa.Column("referrer_host", sa.String(200), nullable=False, server_default=""),
        sa.Column("visitor_hash", sa.String(32), nullable=False, server_default=""),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("is_bot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_page_views_day", "page_views", ["day"])
    op.create_index("ix_page_views_path", "page_views", ["path"])
    op.create_index("ix_page_views_visitor_hash", "page_views", ["visitor_hash"])
    op.create_index("ix_page_views_user_id", "page_views", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "page_views" in tables:
        op.drop_table("page_views")
