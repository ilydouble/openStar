"""add trigram search indexes and english full-text indexes

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-24
"""

from __future__ import annotations

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("DROP INDEX IF EXISTS ix_sessions_title_fts")
    op.execute("DROP INDEX IF EXISTS ix_messages_content_fts")
    op.execute(
        """
        CREATE INDEX ix_sessions_title_fts
        ON sessions
        USING GIN (to_tsvector('english', title))
        """
    )
    op.execute(
        """
        CREATE INDEX ix_messages_content_fts
        ON messages
        USING GIN (to_tsvector('english', content))
        """
    )
    op.execute(
        """
        CREATE INDEX ix_sessions_title_trgm
        ON sessions
        USING GIN (title gin_trgm_ops)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_messages_content_trgm
        ON messages
        USING GIN (content gin_trgm_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_messages_content_trgm")
    op.execute("DROP INDEX IF EXISTS ix_sessions_title_trgm")
    op.execute("DROP INDEX IF EXISTS ix_messages_content_fts")
    op.execute("DROP INDEX IF EXISTS ix_sessions_title_fts")
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
