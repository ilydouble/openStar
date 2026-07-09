"""Repository contract for user file assets."""

from __future__ import annotations

from typing import Protocol

from .models import FileAsset


class FileRepository(Protocol):
    """Persist and retrieve user file assets."""

    def save(self, asset: FileAsset) -> FileAsset:
        """Insert or update one file asset."""
        ...

    def get_by_uuid(self, file_uuid: str) -> FileAsset | None:
        """Load one file asset by UUID."""
        ...

    def list_active_by_checksum(self, checksum_sha256: str) -> list[FileAsset]:
        """Return non-deleted assets that reference a checksum."""
        ...

    def list_active_by_storage_object(
        self,
        *,
        storage_bucket: str,
        object_key: str,
    ) -> list[FileAsset]:
        """Return non-deleted assets that reference one physical object."""
        ...
