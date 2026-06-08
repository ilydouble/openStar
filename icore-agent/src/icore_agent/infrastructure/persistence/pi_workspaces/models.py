"""SQLAlchemy model for persisted Pi Agent uploaded-project workspaces."""

from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..sqlalchemy.base import Base

RowIDType = BigInteger().with_variant(Integer(), "sqlite")

# Lifecycle states for an uploaded workspace archive.
WORKSPACE_STATUS_UPLOADING = "uploading"
WORKSPACE_STATUS_READY = "ready"
WORKSPACE_STATUS_FAILED = "failed"


class PiWorkspace(Base):
    """Persisted metadata for one user-uploaded project archive used by Pi Agent.

    Each row represents a project folder the user uploaded (as a zip archive)
    so the Pi coding agent can analyze it inside a sandboxed, per-workspace
    directory. The archive itself is stored durably in object storage (MinIO
    via the storage-service); this row tracks ownership, integrity and the
    object location so it can be re-extracted into a session workspace later.
    """

    __tablename__ = "pi_workspaces"
    __table_args__ = (
        UniqueConstraint("public_id", name="uq_pi_workspaces_public_id"),
    )

    id: Mapped[int] = mapped_column(RowIDType, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    owner_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "users.public_id",
            name="fk_pi_workspaces_owner_user_id_users",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=WORKSPACE_STATUS_UPLOADING
    )

    # Object-storage location of the uploaded archive (durable copy in MinIO).
    storage_bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    storage_etag: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Integrity + accounting metadata, mirrors the FileAssetRecord pattern.
    checksum_sha256: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    deleted_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
