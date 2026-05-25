"""extend users table for account profiles

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("public_id", sa.String(length=36), nullable=True))
    op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("name", sa.String(length=120), nullable=True))
    op.add_column("users", sa.Column("plan", sa.String(length=40), nullable=False, server_default="free"))
    op.add_column("users", sa.Column("plan_label", sa.String(length=80), nullable=False, server_default="Free"))
    op.add_column("users", sa.Column("organization_id", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("organization_name", sa.String(length=160), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "roles",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[\"owner\"]'::jsonb"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "byok",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text(
                '\'{"enabled": false, "api_key": "", "api_base": "", "model": ""}\'::jsonb'
            ),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "usage",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text(
                '\'{"message_count": 0, "token_count": 0, "image_count": 0, '
                '"attachment_count": 0, "quota_period_start": 0}\'::jsonb'
            ),
        ),
    )
    op.add_column("users", sa.Column("created_at", sa.BigInteger(), nullable=True))
    op.add_column("users", sa.Column("updated_at", sa.BigInteger(), nullable=True))

    op.execute(
        """
        UPDATE users
        SET public_id = COALESCE(public_id, gen_random_uuid()::text),
            email = COALESCE(email, user_name),
            name = COALESCE(name, user_name),
            created_at = COALESCE(created_at, EXTRACT(EPOCH FROM NOW())::bigint),
            updated_at = COALESCE(updated_at, EXTRACT(EPOCH FROM NOW())::bigint)
        """
    )

    op.alter_column("users", "public_id", nullable=False)
    op.alter_column("users", "email", nullable=False)
    op.alter_column("users", "name", nullable=False)
    op.alter_column("users", "created_at", nullable=False)
    op.alter_column("users", "updated_at", nullable=False)
    op.alter_column("users", "password_hash", server_default="")

    op.create_unique_constraint("uq_users_public_id", "users", ["public_id"])
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.create_index("ix_users_organization_id", "users", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_users_organization_id", table_name="users")
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_constraint("uq_users_public_id", "users", type_="unique")
    op.drop_column("users", "updated_at")
    op.drop_column("users", "created_at")
    op.drop_column("users", "usage")
    op.drop_column("users", "byok")
    op.drop_column("users", "roles")
    op.drop_column("users", "organization_name")
    op.drop_column("users", "organization_id")
    op.drop_column("users", "plan_label")
    op.drop_column("users", "plan")
    op.drop_column("users", "name")
    op.drop_column("users", "email")
    op.drop_column("users", "public_id")
