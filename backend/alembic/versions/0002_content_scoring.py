"""content scoring product tables + users.locale

Revision ID: 0002_content_scoring
Revises: 0001_baseline
Create Date: 2026-09-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

import app.models  # noqa: F401
from app.db.base import Base

revision = "0002_content_scoring"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None

_NEW_TABLES = [
    "documents",
    "analyses",
    "dimension_scores",
    "rewrites",
    "feedback",
    "corpus_features",
    "daily_usage",
]


def upgrade() -> None:
    bind = op.get_bind()
    for name in _NEW_TABLES:
        Base.metadata.tables[name].create(bind=bind, checkfirst=True)

    inspector = sa.inspect(bind)
    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "locale" not in user_cols:
        with op.batch_alter_table("users") as batch:
            batch.add_column(
                sa.Column(
                    "locale", sa.String(length=8), nullable=False, server_default="en"
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "locale" in user_cols:
        with op.batch_alter_table("users") as batch:
            batch.drop_column("locale")
    for name in reversed(_NEW_TABLES):
        Base.metadata.tables[name].drop(bind=bind, checkfirst=True)
