"""SQLAlchemy repository for Pi Agent uploaded-project workspaces."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..sqlalchemy.sync_session import sync_session_scope
from .models import PiWorkspace, WORKSPACE_STATUS_READY, WORKSPACE_STATUS_UPLOADING

SessionScope = Callable[[], AbstractContextManager[Session]]


class SqlAlchemyPiWorkspaceRepository:
    """Persist Pi workspace metadata, strictly scoped to its owning user.

    Every read/write method requires the caller's ``owner_user_id`` and
    filters on it — a workspace belonging to one user must never be
    reachable, listable or mutable by another user.
    """

    def __init__(self, session_scope: SessionScope = sync_session_scope) -> None:
        """Create a repository using the provided session scope factory."""
        self._session_scope = session_scope

    def create_pending(
        self,
        *,
        owner_user_id: str,
        title: str,
        storage_bucket: str,
        object_key: str,
        checksum_sha256: str,
        public_id: str | None = None,
    ) -> dict[str, Any]:
        """Insert a new workspace row in the 'uploading' state and return it.

        ``public_id`` may be supplied by the caller when it must be known
        ahead of insertion (e.g. to embed it in the archive's object key).
        """
        now = int(time.time())
        with self._session_scope() as session:
            row = PiWorkspace(
                public_id=public_id or str(uuid.uuid4()),
                owner_user_id=owner_user_id,
                title=title,
                status=WORKSPACE_STATUS_UPLOADING,
                storage_bucket=storage_bucket,
                object_key=object_key,
                storage_etag=None,
                checksum_sha256=checksum_sha256,
                size_bytes=0,
                file_count=0,
                created_at=now,
                updated_at=now,
                deleted_at=None,
            )
            session.add(row)
            session.flush()
            return _serialize(row)

    def mark_ready(
        self,
        *,
        owner_user_id: str,
        public_id: str,
        storage_etag: str | None,
        size_bytes: int,
        file_count: int,
    ) -> dict[str, Any] | None:
        """Mark a workspace as ready for use once its archive is verified."""
        with self._session_scope() as session:
            row = self._get_row(session, owner_user_id=owner_user_id, public_id=public_id)
            if row is None:
                return None
            row.status = WORKSPACE_STATUS_READY
            row.storage_etag = storage_etag
            row.size_bytes = max(int(size_bytes or 0), 0)
            row.file_count = max(int(file_count or 0), 0)
            row.updated_at = int(time.time())
            session.flush()
            return _serialize(row)

    def mark_failed(self, *, owner_user_id: str, public_id: str) -> dict[str, Any] | None:
        """Mark a workspace upload as failed (e.g. checksum mismatch)."""
        with self._session_scope() as session:
            row = self._get_row(session, owner_user_id=owner_user_id, public_id=public_id)
            if row is None:
                return None
            row.status = "failed"
            row.updated_at = int(time.time())
            session.flush()
            return _serialize(row)

    def get_for_owner(self, *, owner_user_id: str, public_id: str) -> dict[str, Any] | None:
        """Load one active workspace, scoped strictly to its owner."""
        with self._session_scope() as session:
            row = self._get_row(session, owner_user_id=owner_user_id, public_id=public_id)
            return _serialize(row) if row is not None else None

    def list_for_owner(self, *, owner_user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Return active workspaces owned by one user, most recent first."""
        with self._session_scope() as session:
            result = session.execute(
                select(PiWorkspace)
                .where(
                    PiWorkspace.owner_user_id == owner_user_id,
                    PiWorkspace.deleted_at.is_(None),
                )
                .order_by(PiWorkspace.updated_at.desc())
                .limit(max(int(limit or 1), 1))
            )
            return [_serialize(row) for row in result.scalars().all()]

    def soft_delete(self, *, owner_user_id: str, public_id: str) -> bool:
        """Soft-delete one workspace owned by the caller; returns False if absent."""
        with self._session_scope() as session:
            row = self._get_row(session, owner_user_id=owner_user_id, public_id=public_id)
            if row is None:
                return False
            now = int(time.time())
            row.deleted_at = now
            row.updated_at = now
            session.flush()
            return True

    @staticmethod
    def _get_row(session: Session, *, owner_user_id: str, public_id: str) -> PiWorkspace | None:
        """Fetch one active workspace row scoped to its owner (internal helper)."""
        result = session.execute(
            select(PiWorkspace).where(
                PiWorkspace.owner_user_id == owner_user_id,
                PiWorkspace.public_id == public_id,
                PiWorkspace.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()


def _serialize(row: PiWorkspace) -> dict[str, Any]:
    """Serialize one workspace row for application/API use."""
    return {
        "id": row.public_id,
        "title": row.title,
        "status": row.status,
        "storage_bucket": row.storage_bucket,
        "object_key": row.object_key,
        "storage_etag": row.storage_etag,
        "checksum_sha256": row.checksum_sha256,
        "size_bytes": row.size_bytes,
        "file_count": row.file_count,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "owner_user_id": row.owner_user_id,
    }
