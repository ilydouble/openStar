"""Application service for persisted file asset workflows."""

from __future__ import annotations

import hashlib
import re
import tempfile
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from icore_agent.contexts.files.domain import FileAsset, FileRepository, uuid7

_CHECKSUM_RE = re.compile(r"^[0-9a-f]{64}$")


class FileAssetNotFoundError(LookupError):
    """Raised when a file asset cannot be loaded for the current user."""


class FileOwnershipError(PermissionError):
    """Raised when a user attempts to access another user's file asset."""


class ChecksumMismatchError(ValueError):
    """Raised when the object bytes do not match the expected SHA-256."""


@dataclass(frozen=True)
class UploadURLResult:
    """Return value for direct upload URL creation."""

    file_uuid: str
    upload_url: str
    expires_in: int


class FileAssetService:
    """Coordinate file metadata persistence with storage-service object access."""

    def __init__(
        self,
        *,
        repository: FileRepository,
        storage_client,
        bucket: str,
        default_expires_in: int,
    ) -> None:
        """Create a service bound to a repository and storage-service client."""
        self._repository = repository
        self._storage_client = storage_client
        self._bucket = bucket
        self._default_expires_in = default_expires_in

    def create_upload_url(
        self,
        *,
        uploader_public_id: str,
        original_filename: str,
        content_type: str,
        checksum_sha256: str,
        expires_in: int | None = None,
    ) -> UploadURLResult:
        """Create a pending file record and return a browser PUT URL."""
        checksum = self._normalize_checksum(checksum_sha256)
        file_uuid = str(uuid7())
        object_key = f"files/{uploader_public_id}/{file_uuid}"
        effective_expires = expires_in or self._default_expires_in

        self._storage_client.ensure_bucket(self._bucket)
        upload_url = self._storage_client.presign_put(
            bucket=self._bucket,
            object_key=object_key,
            content_type=content_type or "application/octet-stream",
            expires_in=effective_expires,
        )
        self._repository.save(
            FileAsset(
                file_uuid=file_uuid,
                original_filename=original_filename.strip() or "upload",
                uploader_public_id=uploader_public_id,
                uploaded_at=self._now(),
                deleted_at=None,
                storage_bucket=self._bucket,
                object_key=object_key,
                storage_etag=None,
                content_type=content_type or "application/octet-stream",
                checksum_sha256=checksum,
            )
        )
        return UploadURLResult(
            file_uuid=file_uuid,
            upload_url=upload_url,
            expires_in=effective_expires,
        )

    @property
    def default_expires_in(self) -> int:
        """Return the default URL expiration in seconds."""
        return self._default_expires_in

    def complete_upload(
        self,
        *,
        uploader_public_id: str,
        file_uuid: str,
        checksum_sha256: str,
    ) -> FileAsset:
        """Verify uploaded bytes and mark the file asset completed."""
        expected_checksum = self._normalize_checksum(checksum_sha256)
        asset = self._require_owned_asset(
            uploader_public_id=uploader_public_id,
            file_uuid=file_uuid,
            allow_pending=True,
        )
        actual_checksum = self._object_checksum(asset)
        if actual_checksum != expected_checksum or actual_checksum != asset.checksum_sha256:
            deleted = asset.mark_deleted(self._now())
            self._repository.save(deleted)
            self._storage_client.delete_object(
                bucket=asset.storage_bucket,
                object_key=asset.object_key,
            )
            raise ChecksumMismatchError(
                "Uploaded file checksum does not match")

        stat = self._storage_client.stat_object(
            bucket=asset.storage_bucket,
            object_key=asset.object_key,
        )
        completed = asset.mark_completed(
            storage_etag=str(stat.get("etag") or ""),
            content_type=str(stat.get("content_type") or asset.content_type),
        )
        canonical = self._canonical_asset_for_checksum(completed)
        if canonical is not None:
            completed = replace(
                completed,
                storage_bucket=canonical.storage_bucket,
                object_key=canonical.object_key,
                storage_etag=canonical.storage_etag,
                content_type=canonical.content_type,
            )
            saved = self._repository.save(completed)
            self._storage_client.delete_object(
                bucket=asset.storage_bucket,
                object_key=asset.object_key,
            )
            return saved
        return self._repository.save(completed)

    def create_download_url(
        self,
        *,
        uploader_public_id: str,
        file_uuid: str,
        expires_in: int | None = None,
    ) -> str:
        """Create a browser GET URL for an owned completed file asset."""
        asset = self._require_owned_asset(
            uploader_public_id=uploader_public_id,
            file_uuid=file_uuid,
            allow_pending=False,
        )
        return self._storage_client.presign_get(
            bucket=asset.storage_bucket,
            object_key=asset.object_key,
            expires_in=expires_in or self._default_expires_in,
        )

    def delete_file(
        self,
        *,
        uploader_public_id: str,
        file_uuid: str,
    ) -> FileAsset:
        """Soft-delete a file asset and remove the object when no active refs remain."""
        asset = self._require_owned_asset(
            uploader_public_id=uploader_public_id,
            file_uuid=file_uuid,
            allow_pending=True,
        )
        deleted = self._repository.save(asset.mark_deleted(self._now()))
        if not self._repository.list_active_by_storage_object(
            storage_bucket=asset.storage_bucket,
            object_key=asset.object_key,
        ):
            self._storage_client.delete_object(
                bucket=asset.storage_bucket,
                object_key=asset.object_key,
            )
        return deleted

    def get_owned_asset(
        self,
        *,
        uploader_public_id: str,
        file_uuid: str,
        allow_pending: bool = False,
    ) -> FileAsset:
        """Return one owned file asset or raise a not-found style error."""
        return self._require_owned_asset(
            uploader_public_id=uploader_public_id,
            file_uuid=file_uuid,
            allow_pending=allow_pending,
        )

    def read_file_bytes(self, *, uploader_public_id: str, file_uuid: str) -> bytes:
        """Read the full object bytes for a completed file asset."""
        asset = self._require_owned_asset(
            uploader_public_id=uploader_public_id,
            file_uuid=file_uuid,
            allow_pending=False,
        )
        return b"".join(
            self._storage_client.get_object_stream(
                bucket=asset.storage_bucket,
                object_key=asset.object_key,
            )
        )

    def materialize_temp_file(
        self,
        *,
        uploader_public_id: str,
        file_uuid: str,
    ) -> tuple[FileAsset, Path]:
        """Copy an owned object to a temporary local file and return its path."""
        asset = self._require_owned_asset(
            uploader_public_id=uploader_public_id,
            file_uuid=file_uuid,
            allow_pending=False,
        )
        suffix = Path(asset.original_filename).suffix
        handle = tempfile.NamedTemporaryFile(
            prefix=f"icore-file-{asset.file_uuid}-",
            suffix=suffix,
            delete=False,
        )
        with handle:
            for chunk in self._storage_client.get_object_stream(
                bucket=asset.storage_bucket,
                object_key=asset.object_key,
            ):
                handle.write(chunk)
        return asset, Path(handle.name)

    def _require_owned_asset(
        self,
        *,
        uploader_public_id: str,
        file_uuid: str,
        allow_pending: bool,
    ) -> FileAsset:
        """Load a non-deleted asset owned by the current user."""
        asset = self._repository.get_by_uuid(file_uuid)
        if asset is None or asset.deleted_at is not None:
            raise FileAssetNotFoundError(file_uuid)
        if asset.uploader_public_id != uploader_public_id:
            raise FileAssetNotFoundError(file_uuid)
        if not allow_pending and not asset.storage_etag:
            raise FileAssetNotFoundError(file_uuid)
        return asset

    def _object_checksum(self, asset: FileAsset) -> str:
        """Compute SHA-256 from storage-service object bytes."""
        digest = hashlib.sha256()
        for chunk in self._storage_client.get_object_stream(
            bucket=asset.storage_bucket,
            object_key=asset.object_key,
        ):
            digest.update(chunk)
        return digest.hexdigest()

    def _canonical_asset_for_checksum(self, asset: FileAsset) -> FileAsset | None:
        """Return an existing completed asset that already owns this checksum."""
        for candidate in self._repository.list_active_by_checksum(
            asset.checksum_sha256,
        ):
            if candidate.file_uuid == asset.file_uuid:
                continue
            if candidate.storage_etag:
                return candidate
        return None

    def _normalize_checksum(self, checksum_sha256: str) -> str:
        """Validate and normalize a SHA-256 checksum string."""
        checksum = checksum_sha256.strip().lower()
        if not _CHECKSUM_RE.fullmatch(checksum):
            raise ValueError(
                "checksum_sha256 must be a 64-character lowercase hex SHA-256")
        return checksum

    def _now(self) -> datetime:
        """Return the current timezone-aware UTC timestamp."""
        return datetime.now(UTC)
