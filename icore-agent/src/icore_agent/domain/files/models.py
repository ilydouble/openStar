"""Domain model for user-owned file assets."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime


@dataclass(frozen=True)
class FileAsset:
    """Represent one user-owned logical file record."""

    file_uuid: str
    original_filename: str
    uploader_public_id: str
    uploaded_at: datetime
    deleted_at: datetime | None
    storage_bucket: str
    object_key: str
    storage_etag: str | None
    content_type: str
    checksum_sha256: str

    def mark_completed(self, *, storage_etag: str, content_type: str) -> "FileAsset":
        """Return a completed copy with storage metadata applied."""
        return replace(
            self,
            storage_etag=storage_etag,
            content_type=content_type or self.content_type,
        )

    def mark_deleted(self, deleted_at: datetime) -> "FileAsset":
        """Return a soft-deleted copy of this file asset."""
        return replace(self, deleted_at=deleted_at)
