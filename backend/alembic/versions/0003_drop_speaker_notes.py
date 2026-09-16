"""drop speaker-notes tables (pivot to content scoring)

Revision ID: 0003_drop_speaker_notes
Revises: 0002_content_scoring
Create Date: 2026-09-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_drop_speaker_notes"
down_revision = "0002_content_scoring"
branch_labels = None
depends_on = None

_DROP = ["page_revisions", "pages", "sections", "generation_logs", "projects"]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())
    for name in _DROP:
        if name in existing:
            op.drop_table(name)


def downgrade() -> None:
    # Irreversible (the speaker-notes schema is retired).
    pass
