from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC
from io import BytesIO

import pytest

from icore_agent.application.files.service import (
    ChecksumMismatchError,
    FileAssetService,
)
from icore_agent.domain.files.models import FileAsset
from icore_agent.domain.files.uuid import uuid7


class MemoryFileRepository:
    """In-memory repository used to verify file asset service behavior."""

    def __init__(self) -> None:
        """Initialize an empty repository."""
        self.assets: dict[str, FileAsset] = {}

    def save(self, asset: FileAsset) -> FileAsset:
        """Persist one file asset record."""
        self.assets[str(asset.file_uuid)] = asset
        return asset

    def get_by_uuid(self, file_uuid: str) -> FileAsset | None:
        """Load a file asset by UUID."""
        return self.assets.get(str(file_uuid))

    def list_active_by_checksum(self, checksum_sha256: str) -> list[FileAsset]:
        """Return active assets with the same checksum."""
        return [
            asset
            for asset in self.assets.values()
            if asset.checksum_sha256 == checksum_sha256 and asset.deleted_at is None
        ]

    def list_active_by_storage_object(
        self,
        *,
        storage_bucket: str,
        object_key: str,
    ) -> list[FileAsset]:
        """Return active assets that point at one storage object."""
        return [
            asset
            for asset in self.assets.values()
            if (
                asset.storage_bucket == storage_bucket
                and asset.object_key == object_key
                and asset.deleted_at is None
            )
        ]


class FakeStorageClient:
    """Storage client fake with deterministic presigned URLs and object bytes."""

    def __init__(self, body: bytes) -> None:
        """Initialize the fake with one readable object payload."""
        self.body = body
        self.deleted: list[tuple[str, str]] = []

    def ensure_bucket(self, bucket: str) -> None:
        """Accept all buckets."""

    def presign_put(
        self,
        *,
        bucket: str,
        object_key: str,
        content_type: str,
        expires_in: int,
    ) -> str:
        """Return a deterministic upload URL."""
        return f"https://storage.example.com/{bucket}/{object_key}?put=1"

    def presign_get(self, *, bucket: str, object_key: str, expires_in: int) -> str:
        """Return a deterministic download URL."""
        return f"https://storage.example.com/{bucket}/{object_key}?get=1"

    def stat_object(self, *, bucket: str, object_key: str) -> dict:
        """Return object metadata after a fake upload."""
        return {
            "bucket": bucket,
            "object_key": object_key,
            "etag": "etag-123",
            "content_type": "text/plain",
        }

    def get_object_stream(self, *, bucket: str, object_key: str) -> Iterator[bytes]:
        """Stream the fake object bytes."""
        yield self.body

    def open_object(self, *, bucket: str, object_key: str) -> BytesIO:
        """Open the fake object bytes as a file-like object."""
        return BytesIO(self.body)

    def delete_object(self, *, bucket: str, object_key: str) -> None:
        """Record object deletion."""
        self.deleted.append((bucket, object_key))


def test_uuid7_returns_parseable_time_ordered_values() -> None:
    """UUIDv7 generation should be parseable and roughly time ordered."""
    first = uuid7()
    second = uuid7()

    assert first.version == 7
    assert second.version == 7
    assert first.int < second.int


def test_create_upload_url_persists_default_object_key() -> None:
    """Creating an upload URL should create a pending asset record."""
    body = b"hello world"
    checksum = hashlib.sha256(body).hexdigest()
    repo = MemoryFileRepository()
    service = FileAssetService(
        repository=repo,
        storage_client=FakeStorageClient(body),
        bucket="icore-files",
        default_expires_in=600,
    )

    result = service.create_upload_url(
        uploader_public_id="user-public-id",
        original_filename="brief.txt",
        content_type="text/plain",
        checksum_sha256=checksum,
    )

    asset = repo.get_by_uuid(result.file_uuid)
    assert asset is not None
    assert result.expires_in == 600
    assert result.upload_url.startswith(
        f"https://storage.example.com/icore-files/files/user-public-id/{result.file_uuid}"
    )
    assert asset.object_key == f"files/user-public-id/{result.file_uuid}"
    assert asset.storage_etag is None
    assert asset.uploaded_at.tzinfo is not None


def test_complete_upload_verifies_server_side_checksum() -> None:
    """Completing an upload should trust the server-computed object checksum."""
    body = b"trusted content"
    checksum = hashlib.sha256(body).hexdigest()
    repo = MemoryFileRepository()
    service = FileAssetService(
        repository=repo,
        storage_client=FakeStorageClient(body),
        bucket="icore-files",
        default_expires_in=600,
    )
    created = service.create_upload_url(
        uploader_public_id="user-public-id",
        original_filename="brief.txt",
        content_type="text/plain",
        checksum_sha256=checksum,
    )

    completed = service.complete_upload(
        uploader_public_id="user-public-id",
        file_uuid=created.file_uuid,
        checksum_sha256=checksum,
    )

    assert completed.storage_etag == "etag-123"
    assert completed.deleted_at is None
    assert completed.uploaded_at.tzinfo is not None


def test_complete_upload_reuses_existing_physical_object_for_same_checksum() -> None:
    """Duplicate checksums should keep separate rows but share one stored object."""
    body = b"same content"
    checksum = hashlib.sha256(body).hexdigest()
    repo = MemoryFileRepository()
    storage = FakeStorageClient(body)
    service = FileAssetService(
        repository=repo,
        storage_client=storage,
        bucket="icore-files",
        default_expires_in=600,
    )
    first = service.create_upload_url(
        uploader_public_id="user-one",
        original_filename="first.txt",
        content_type="text/plain",
        checksum_sha256=checksum,
    )
    first_completed = service.complete_upload(
        uploader_public_id="user-one",
        file_uuid=first.file_uuid,
        checksum_sha256=checksum,
    )
    second = service.create_upload_url(
        uploader_public_id="user-two",
        original_filename="second.txt",
        content_type="text/plain",
        checksum_sha256=checksum,
    )
    second_upload_key = f"files/user-two/{second.file_uuid}"

    second_completed = service.complete_upload(
        uploader_public_id="user-two",
        file_uuid=second.file_uuid,
        checksum_sha256=checksum,
    )

    assert second_completed.file_uuid != first_completed.file_uuid
    assert second_completed.object_key == first_completed.object_key
    assert second_completed.storage_etag == first_completed.storage_etag
    assert second_completed.original_filename == "second.txt"
    assert storage.deleted == [("icore-files", second_upload_key)]


def test_delete_file_removes_shared_object_only_after_last_reference() -> None:
    """Deleting one reference should not remove an object still referenced elsewhere."""
    body = b"same content"
    checksum = hashlib.sha256(body).hexdigest()
    repo = MemoryFileRepository()
    storage = FakeStorageClient(body)
    service = FileAssetService(
        repository=repo,
        storage_client=storage,
        bucket="icore-files",
        default_expires_in=600,
    )
    first = service.create_upload_url(
        uploader_public_id="user-one",
        original_filename="first.txt",
        content_type="text/plain",
        checksum_sha256=checksum,
    )
    first_completed = service.complete_upload(
        uploader_public_id="user-one",
        file_uuid=first.file_uuid,
        checksum_sha256=checksum,
    )
    second = service.create_upload_url(
        uploader_public_id="user-two",
        original_filename="second.txt",
        content_type="text/plain",
        checksum_sha256=checksum,
    )
    second_completed = service.complete_upload(
        uploader_public_id="user-two",
        file_uuid=second.file_uuid,
        checksum_sha256=checksum,
    )
    storage.deleted.clear()

    service.delete_file(
        uploader_public_id="user-two",
        file_uuid=second_completed.file_uuid,
    )
    assert storage.deleted == []

    service.delete_file(
        uploader_public_id="user-one",
        file_uuid=first_completed.file_uuid,
    )
    assert storage.deleted == [("icore-files", first_completed.object_key)]


def test_complete_upload_rejects_checksum_mismatch_and_soft_deletes_record() -> None:
    """Checksum mismatch should reject the upload and mark the row deleted."""
    body = b"actual content"
    repo = MemoryFileRepository()
    storage = FakeStorageClient(body)
    service = FileAssetService(
        repository=repo,
        storage_client=storage,
        bucket="icore-files",
        default_expires_in=600,
    )
    created = service.create_upload_url(
        uploader_public_id="user-public-id",
        original_filename="brief.txt",
        content_type="text/plain",
        checksum_sha256="0" * 64,
    )

    with pytest.raises(ChecksumMismatchError):
        service.complete_upload(
            uploader_public_id="user-public-id",
            file_uuid=created.file_uuid,
            checksum_sha256="0" * 64,
        )

    asset = repo.get_by_uuid(created.file_uuid)
    assert asset is not None
    assert asset.deleted_at is not None
    assert asset.deleted_at.tzinfo is not None
    assert asset.deleted_at.tzinfo.utcoffset(
        asset.deleted_at) == UTC.utcoffset(None)
    assert storage.deleted == [("icore-files", asset.object_key)]
