"""create llm tool calls table

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_tool_calls",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("assistant_message_id", sa.BigInteger(), nullable=True),
        sa.Column("tool_message_id", sa.BigInteger(), nullable=True),
        sa.Column("tool_call_id", sa.Text(), nullable=False),
        sa.Column("tool_type", sa.Text(), nullable=False,
                  server_default="function"),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column(
            "arguments",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("result", postgresql.JSONB(
            astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("elapsed_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            name="fk_llm_tool_calls_session_id_sessions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["assistant_message_id"],
            ["messages.id"],
            name="fk_llm_tool_calls_assistant_message_id_messages",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tool_message_id"],
            ["messages.id"],
            name="fk_llm_tool_calls_tool_message_id_messages",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_llm_tool_calls_session_id",
        "llm_tool_calls",
        ["session_id"],
    )
    op.create_index(
        "ix_llm_tool_calls_assistant_message_id",
        "llm_tool_calls",
        ["assistant_message_id"],
    )
    op.create_index(
        "ix_llm_tool_calls_tool_message_id",
        "llm_tool_calls",
        ["tool_message_id"],
    )
    op.create_index(
        "ix_llm_tool_calls_tool_call_id",
        "llm_tool_calls",
        ["tool_call_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_llm_tool_calls_tool_call_id",
                  table_name="llm_tool_calls")
    op.drop_index("ix_llm_tool_calls_tool_message_id",
                  table_name="llm_tool_calls")
    op.drop_index("ix_llm_tool_calls_assistant_message_id",
                  table_name="llm_tool_calls")
    op.drop_index("ix_llm_tool_calls_session_id",
                  table_name="llm_tool_calls")
    op.drop_table("llm_tool_calls")
