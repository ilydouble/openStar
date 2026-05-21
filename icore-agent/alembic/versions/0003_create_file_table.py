"""create files table for user file assets

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "files",
        sa.Column("file_uuid", postgresql.UUID(
            as_uuid=True), primary_key=True),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("uploader_public_id", sa.String(length=36), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("storage_bucket", sa.String(length=255), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("storage_etag", sa.Text(), nullable=True),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("checksum_sha256", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["uploader_public_id"],
            ["users.public_id"],
            name="fk_files_uploader_public_id_users",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_files_uploader_public_id",
                    "files", ["uploader_public_id"])
    op.create_index("ix_files_checksum_sha256", "files", ["checksum_sha256"])
    op.create_index("ix_files_deleted_at", "files", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_files_deleted_at", table_name="files")
    op.drop_index("ix_files_checksum_sha256", table_name="files")
    op.drop_index("ix_files_uploader_public_id", table_name="files")
    op.drop_table("files")
