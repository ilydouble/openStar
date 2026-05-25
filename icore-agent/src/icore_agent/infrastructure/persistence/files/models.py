"""SQLAlchemy model for persisted user file assets."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..sqlalchemy.base import Base

FileUUIDType = UUID(as_uuid=False).with_variant(String(36), "sqlite")


class FileAssetRecord(Base):
    """Persisted file asset metadata row."""

    __tablename__ = "files"
    file_uuid: Mapped[str] = mapped_column(FileUUIDType, primary_key=True)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    uploader_public_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.public_id",
                   name="fk_files_uploader_public_id_users"),
        nullable=False,
        index=True,
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True)
    storage_bucket: Mapped[str] = mapped_column(
        String(255), nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    storage_etag: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(
        Text, nullable=False, index=True)
