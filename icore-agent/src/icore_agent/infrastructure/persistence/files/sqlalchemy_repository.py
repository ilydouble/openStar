"""SQLAlchemy implementation of the file repository contract."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager

from sqlalchemy import select
from sqlalchemy.orm import Session

from icore_agent.domain.files import FileAsset

from ..sqlalchemy.sync_session import sync_session_scope
from .models import FileAssetRecord

SessionScope = Callable[[], AbstractContextManager[Session]]


class SqlAlchemyFileRepository:
    """Persist file assets through scoped synchronous SQLAlchemy sessions."""

    def __init__(
        self,
        session_scope: SessionScope = sync_session_scope,
    ) -> None:
        """Create a repository using the provided session scope factory."""
        self._session_scope = session_scope

    def save(self, asset: FileAsset) -> FileAsset:
        """Insert or update one file asset."""
        with self._session_scope() as session:
            row = session.get(FileAssetRecord, asset.file_uuid)
            if row is None:
                row = FileAssetRecord(file_uuid=asset.file_uuid)
                session.add(row)
            _apply_asset(row, asset)
            session.flush()
            return _to_asset(row)

    def get_by_uuid(self, file_uuid: str) -> FileAsset | None:
        """Load one file asset by UUID."""
        with self._session_scope() as session:
            row = session.get(FileAssetRecord, str(file_uuid))
            return _to_asset(row) if row is not None else None

    def list_active_by_checksum(self, checksum_sha256: str) -> list[FileAsset]:
        """Return active file assets that share a checksum."""
        with self._session_scope() as session:
            result = session.execute(
                select(FileAssetRecord)
                .where(
                    FileAssetRecord.checksum_sha256 == checksum_sha256,
                    FileAssetRecord.deleted_at.is_(None),
                )
                .order_by(FileAssetRecord.uploaded_at.asc())
            )
            return [_to_asset(row) for row in result.scalars().all()]

    def list_active_by_storage_object(
        self,
        *,
        storage_bucket: str,
        object_key: str,
    ) -> list[FileAsset]:
        """Return active file assets that reference one stored object."""
        with self._session_scope() as session:
            result = session.execute(
                select(FileAssetRecord)
                .where(
                    FileAssetRecord.storage_bucket == storage_bucket,
                    FileAssetRecord.object_key == object_key,
                    FileAssetRecord.deleted_at.is_(None),
                )
                .order_by(FileAssetRecord.uploaded_at.asc())
            )
            return [_to_asset(row) for row in result.scalars().all()]


def _apply_asset(row: FileAssetRecord, asset: FileAsset) -> None:
    """Copy domain file fields onto an ORM row."""
    row.original_filename = asset.original_filename
    row.uploader_public_id = asset.uploader_public_id
    row.uploaded_at = asset.uploaded_at
    row.deleted_at = asset.deleted_at
    row.storage_bucket = asset.storage_bucket
    row.object_key = asset.object_key
    row.storage_etag = asset.storage_etag
    row.content_type = asset.content_type
    row.checksum_sha256 = asset.checksum_sha256


def _to_asset(row: FileAssetRecord) -> FileAsset:
    """Convert an ORM row into a domain file asset."""
    return FileAsset(
        file_uuid=str(row.file_uuid),
        original_filename=row.original_filename,
        uploader_public_id=row.uploader_public_id,
        uploaded_at=row.uploaded_at,
        deleted_at=row.deleted_at,
        storage_bucket=row.storage_bucket,
        object_key=row.object_key,
        storage_etag=row.storage_etag,
        content_type=row.content_type,
        checksum_sha256=row.checksum_sha256,
    )
