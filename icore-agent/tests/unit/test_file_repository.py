from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from icore_agent.contexts.files.domain.models import FileAsset
from icore_agent.contexts.files.infrastructure.persistence.sqlalchemy_repository import (
    SqlAlchemyFileRepository,
)
from icore_agent.infrastructure.persistence.sqlalchemy.models import Base


def test_file_repository_allows_multiple_rows_for_one_physical_object() -> None:
    """Logical file records should be able to share one storage object."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    @contextmanager
    def session_scope():
        """Open one transactional SQLAlchemy session for the test repository."""
        with Session(engine) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    repo = SqlAlchemyFileRepository(session_scope)
    checksum = "a" * 64
    object_key = "files/user-one/shared-object"

    first = repo.save(
        _asset(
            file_uuid=str(uuid4()),
            uploader_public_id="user-one",
            original_filename="first.txt",
            object_key=object_key,
            checksum=checksum,
        )
    )
    second = repo.save(
        _asset(
            file_uuid=str(uuid4()),
            uploader_public_id="user-two",
            original_filename="second.txt",
            object_key=object_key,
            checksum=checksum,
        )
    )

    refs = repo.list_active_by_checksum(checksum)
    object_refs = repo.list_active_by_storage_object(
        storage_bucket="icore-files",
        object_key=object_key,
    )
    assert {asset.file_uuid for asset in refs} == {
        first.file_uuid,
        second.file_uuid,
    }
    assert {asset.object_key for asset in refs} == {object_key}
    assert {asset.file_uuid for asset in object_refs} == {
        first.file_uuid,
        second.file_uuid,
    }


def _asset(
    *,
    file_uuid: str,
    uploader_public_id: str,
    original_filename: str,
    object_key: str,
    checksum: str,
) -> FileAsset:
    """Build a completed file asset for repository tests."""
    return FileAsset(
        file_uuid=file_uuid,
        original_filename=original_filename,
        uploader_public_id=uploader_public_id,
        uploaded_at=datetime.now(UTC),
        deleted_at=None,
        storage_bucket="icore-files",
        object_key=object_key,
        storage_etag="etag-123",
        content_type="text/plain",
        checksum_sha256=checksum,
    )
