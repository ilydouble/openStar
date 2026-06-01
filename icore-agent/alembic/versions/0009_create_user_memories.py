"""create user memory profiles and facts tables

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_memory_profiles",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column(
            "profile",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("maintenance_version", sa.Integer(),
                  nullable=False, server_default="0"),
        sa.Column("extract_count", sa.Integer(),
                  nullable=False, server_default="0"),
        sa.Column("turns_since_extract", sa.Integer(),
                  nullable=False, server_default="0"),
        sa.Column("last_maintained_at", sa.BigInteger(),
                  nullable=False, server_default="0"),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.public_id"],
            name="fk_user_memory_profiles_user_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_user_memory_profiles"),
    )

    op.create_table(
        "user_memory_facts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16),
                  nullable=False, server_default="active"),
        sa.Column("source", sa.String(length=16),
                  nullable=False, server_default="inferred"),
        sa.Column("confidence", sa.Float(),
                  nullable=False, server_default="0.5"),
        sa.Column("salience", sa.Float(),
                  nullable=False, server_default="0.5"),
        sa.Column("access_count", sa.Integer(),
                  nullable=False, server_default="0"),
        sa.Column("last_accessed_at", sa.BigInteger(),
                  nullable=False, server_default="0"),
        sa.Column("last_confirmed_at", sa.BigInteger(),
                  nullable=False, server_default="0"),
        sa.Column("expires_at", sa.BigInteger(), nullable=True),
        sa.Column("supersedes_id", sa.BigInteger(), nullable=True),
        sa.Column("source_session_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.public_id"],
            name="fk_user_memory_facts_user_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["user_memory_facts.id"],
            name="fk_user_memory_facts_supersedes_id",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_user_memory_facts_user_status",
        "user_memory_facts",
        ["user_id", "status"],
    )
    op.create_index(
        "ix_user_memory_facts_user_category_key",
        "user_memory_facts",
        ["user_id", "category", "key"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_memory_facts_user_category_key",
                  table_name="user_memory_facts")
    op.drop_index("ix_user_memory_facts_user_status",
                  table_name="user_memory_facts")
    op.drop_table("user_memory_facts")
    op.drop_table("user_memory_profiles")
