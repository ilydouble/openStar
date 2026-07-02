"""create commerce_diagnoses table

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "commerce_diagnoses",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("diagnosis_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("agent_profile", sa.String(length=80), nullable=False),
        sa.Column(
            "source_file",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "risks",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "tasks",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("report_summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.public_id"],
            name="fk_commerce_diagnoses_user_id_users",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "diagnosis_id",
            name="uq_commerce_diagnoses_diagnosis_id",
        ),
    )
    op.create_index(
        "ix_commerce_diagnoses_diagnosis_id",
        "commerce_diagnoses",
        ["diagnosis_id"],
    )
    op.create_index(
        "ix_commerce_diagnoses_user_id",
        "commerce_diagnoses",
        ["user_id"],
    )
    op.create_index(
        "ix_commerce_diagnoses_created_at",
        "commerce_diagnoses",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_commerce_diagnoses_created_at",
                  table_name="commerce_diagnoses")
    op.drop_index("ix_commerce_diagnoses_user_id",
                  table_name="commerce_diagnoses")
    op.drop_index("ix_commerce_diagnoses_diagnosis_id",
                  table_name="commerce_diagnoses")
    op.drop_table("commerce_diagnoses")
