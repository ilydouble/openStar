"""create session events table

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "session_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("turn_id", sa.BigInteger(), nullable=False),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("item_public_id", sa.String(length=36), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            name="fk_session_events_session_id_sessions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["turn_id"],
            ["turns.id"],
            name="fk_session_events_turn_id_turns",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "turn_id",
            "public_id",
            name="uq_session_events_turn_public_id",
        ),
        sa.UniqueConstraint(
            "turn_id",
            "sequence",
            name="uq_session_events_turn_sequence",
        ),
    )
    op.create_index("ix_session_events_session_id",
                    "session_events", ["session_id"])
    op.create_index("ix_session_events_turn_id",
                    "session_events", ["turn_id"])
    op.create_index(
        "ix_session_events_session_id_id",
        "session_events",
        ["session_id", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_session_events_session_id_id",
                  table_name="session_events")
    op.drop_index("ix_session_events_turn_id", table_name="session_events")
    op.drop_index("ix_session_events_session_id", table_name="session_events")
    op.drop_table("session_events")
