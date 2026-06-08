"""create turns and session items tables

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "turns",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("error", postgresql.JSONB(
            astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            name="fk_turns_session_id_sessions",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("public_id", name="uq_turns_public_id"),
    )
    op.create_index("ix_turns_session_id", "turns", ["session_id"])

    op.create_table(
        "session_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("turn_id", sa.BigInteger(), nullable=False),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("item_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            name="fk_session_items_session_id_sessions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["turn_id"],
            ["turns.id"],
            name="fk_session_items_turn_id_turns",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "turn_id",
            "public_id",
            name="uq_session_items_turn_public_id",
        ),
        sa.UniqueConstraint(
            "turn_id",
            "sequence",
            name="uq_session_items_turn_sequence",
        ),
    )
    op.create_index("ix_session_items_session_id",
                    "session_items", ["session_id"])
    op.create_index("ix_session_items_turn_id", "session_items", ["turn_id"])


def downgrade() -> None:
    op.drop_index("ix_session_items_turn_id", table_name="session_items")
    op.drop_index("ix_session_items_session_id", table_name="session_items")
    op.drop_table("session_items")
    op.drop_index("ix_turns_session_id", table_name="turns")
    op.drop_table("turns")
