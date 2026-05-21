"""add full-text search indexes for sessions and messages

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-20
"""

from __future__ import annotations

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX ix_sessions_title_fts
        ON sessions
        USING GIN (to_tsvector('simple', title))
        """
    )
    op.execute(
        """
        CREATE INDEX ix_messages_content_fts
        ON messages
        USING GIN (to_tsvector('simple', content))
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_messages_content_fts")
    op.execute("DROP INDEX IF EXISTS ix_sessions_title_fts")
