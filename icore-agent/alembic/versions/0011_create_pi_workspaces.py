"""create pi_workspaces table for Pi Agent uploaded-project archives

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pi_workspaces",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("owner_user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False,
                  server_default="uploading"),
        sa.Column("storage_bucket", sa.String(length=255), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("storage_etag", sa.Text(), nullable=True),
        sa.Column("checksum_sha256", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("file_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.Column("deleted_at", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.public_id"],
            name="fk_pi_workspaces_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("public_id", name="uq_pi_workspaces_public_id"),
    )
    op.create_index("ix_pi_workspaces_public_id", "pi_workspaces", ["public_id"])
    op.create_index("ix_pi_workspaces_owner_user_id", "pi_workspaces", ["owner_user_id"])
    op.create_index("ix_pi_workspaces_checksum_sha256", "pi_workspaces", ["checksum_sha256"])
    op.create_index("ix_pi_workspaces_deleted_at", "pi_workspaces", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_pi_workspaces_deleted_at", table_name="pi_workspaces")
    op.drop_index("ix_pi_workspaces_checksum_sha256", table_name="pi_workspaces")
    op.drop_index("ix_pi_workspaces_owner_user_id", table_name="pi_workspaces")
    op.drop_index("ix_pi_workspaces_public_id", table_name="pi_workspaces")
    op.drop_table("pi_workspaces")


