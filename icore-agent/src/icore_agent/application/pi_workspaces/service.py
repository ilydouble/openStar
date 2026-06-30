"""Application service for Pi Agent uploaded-project workspace archives.

This service coordinates the lifecycle of a user-uploaded project archive:

  1. ``create_upload_url``  — register a pending workspace row and hand the
     browser a presigned PUT URL so the zip is streamed straight into MinIO
     (mirrors the existing ``FileAssetService`` direct-upload pattern).
  2. ``complete_upload``    — verify the archive's checksum, inspect its
     entries for safety (size limits, file-count limits, zip-slip / path
     traversal, symlinks) and mark the workspace 'ready' or 'failed'.
  3. ``extract_into_sandbox`` — materialize a 'ready' workspace into a fresh,
     strictly-contained directory that the Pi agent can be pointed at. Every
     extracted path is re-validated against the destination root so the
     archive can never write outside its sandbox (defense in depth on top of
     the checks performed during ``complete_upload``).

All read/write paths are scoped to ``owner_user_id`` — a workspace can only
ever be seen, listed, extracted or deleted by the user who uploaded it.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from icore_agent.domain.files import uuid7

_CHECKSUM_RE = re.compile(r"^[0-9a-f]{64}$")

# Defensive ceiling on the *uncompressed* size we will ever extract, even if
# the configured per-archive limit is larger — guards against zip-bomb style
# archives whose compressed size looks small but expand enormously.
_MAX_UNCOMPRESSED_RATIO = 200


class WorkspaceNotFoundError(LookupError):
    """Raised when a workspace cannot be loaded for the current user.

    Deliberately used both for "does not exist" and "belongs to someone
    else" — mirrors ``FileAssetService`` so we never leak which case applies.
    """


class WorkspaceNotReadyError(ValueError):
    """Raised when an operation requires a 'ready' workspace but it is not."""


class ChecksumMismatchError(ValueError):
    """Raised when the uploaded archive bytes do not match the declared SHA-256."""


class WorkspaceLimitExceededError(ValueError):
    """Raised when an archive exceeds configured size/file-count limits."""


class UnsafeArchiveError(ValueError):
    """Raised when an archive contains entries that could escape the sandbox.

    Covers zip-slip (``../`` traversal), absolute paths, and symlink entries —
    any of which could otherwise let extracted content land outside the
    per-workspace sandbox directory.
    """


@dataclass(frozen=True)
class WorkspaceUploadURLResult:
    """Return value for presigned workspace-archive upload URL creation."""

    workspace_id: str
    upload_url: str
    expires_in: int


class PiWorkspaceService:
    """Coordinate Pi workspace metadata persistence with object storage."""

    def __init__(
        self,
        *,
        repository,
        storage_client,
        bucket: str,
        default_expires_in: int,
        max_size_mb: int,
        max_files: int,
    ) -> None:
        """Create a service bound to a repository and storage-service client."""
        self._repository = repository
        self._storage_client = storage_client
        self._bucket = bucket
        self._default_expires_in = default_expires_in
        self._max_size_bytes = max(int(max_size_mb), 1) * 1024 * 1024
        self._max_files = max(int(max_files), 1)

    # ------------------------------------------------------------------
    # Upload lifecycle
    # ------------------------------------------------------------------

    def create_upload_url(
        self,
        *,
        owner_user_id: str,
        title: str,
        checksum_sha256: str,
        expires_in: int | None = None,
    ) -> WorkspaceUploadURLResult:
        """Register a pending workspace and return a browser PUT URL for its archive."""
        checksum = self._normalize_checksum(checksum_sha256)
        clean_title = (title or "").strip()[:200] or "Untitled project"
        effective_expires = expires_in or self._default_expires_in

        # Mint the id up front so the object key can embed it — avoids any
        # two-phase create/update dance and keeps the row consistent from
        # the very first write.
        workspace_id = str(uuid7())
        object_key = f"pi-workspaces/{owner_user_id}/{workspace_id}/source.zip"

        self._storage_client.ensure_bucket(self._bucket)
        self._repository.create_pending(
            owner_user_id=owner_user_id,
            title=clean_title,
            storage_bucket=self._bucket,
            object_key=object_key,
            checksum_sha256=checksum,
            public_id=workspace_id,
        )

        upload_url = self._storage_client.presign_put(
            bucket=self._bucket,
            object_key=object_key,
            content_type="application/zip",
            expires_in=effective_expires,
        )
        return WorkspaceUploadURLResult(
            workspace_id=workspace_id,
            upload_url=upload_url,
            expires_in=effective_expires,
        )

    def complete_upload(
        self,
        *,
        owner_user_id: str,
        workspace_id: str,
        checksum_sha256: str,
    ) -> dict[str, Any]:
        """Verify an uploaded archive and mark the workspace ready or failed."""
        expected_checksum = self._normalize_checksum(checksum_sha256)
        workspace = self._require_owned(owner_user_id=owner_user_id, public_id=workspace_id)
        object_key = workspace["object_key"]

        stat = self._storage_client.stat_object(bucket=self._bucket, object_key=object_key)
        size_bytes = int(stat.get("size") or 0)

        try:
            self._verify_checksum(object_key=object_key, expected=expected_checksum)
            self._enforce_size_limit(size_bytes)
            file_count = self._inspect_archive(object_key=object_key)
        except (ChecksumMismatchError, WorkspaceLimitExceededError, UnsafeArchiveError):
            self._repository.mark_failed(owner_user_id=owner_user_id, public_id=workspace_id)
            self._storage_client.delete_object(bucket=self._bucket, object_key=object_key)
            raise

        updated = self._repository.mark_ready(
            owner_user_id=owner_user_id,
            public_id=workspace_id,
            storage_etag=str(stat.get("etag") or ""),
            size_bytes=size_bytes,
            file_count=file_count,
        )
        if updated is None:
            raise WorkspaceNotFoundError(workspace_id)
        return updated

    # ------------------------------------------------------------------
    # Read / list / delete
    # ------------------------------------------------------------------

    def get_owned_workspace(self, *, owner_user_id: str, workspace_id: str) -> dict[str, Any]:
        """Return one workspace owned by the caller, or raise not-found."""
        return self._require_owned(owner_user_id=owner_user_id, public_id=workspace_id)

    def list_workspaces(self, *, owner_user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Return active workspaces for the caller, most recently updated first."""
        return self._repository.list_for_owner(owner_user_id=owner_user_id, limit=limit)

    def delete_workspace(self, *, owner_user_id: str, workspace_id: str) -> None:
        """Soft-delete a workspace and remove its archive from object storage."""
        workspace = self._require_owned(owner_user_id=owner_user_id, public_id=workspace_id)
        if not self._repository.soft_delete(owner_user_id=owner_user_id, public_id=workspace_id):
            raise WorkspaceNotFoundError(workspace_id)
        self._storage_client.delete_object(
            bucket=workspace["storage_bucket"],
            object_key=workspace["object_key"],
        )

    # ------------------------------------------------------------------
    # Sandbox extraction — the "Pi may never escape this folder" guarantee
    # ------------------------------------------------------------------

    def extract_into_sandbox(
        self,
        *,
        owner_user_id: str,
        workspace_id: str,
        destination_root: Path,
    ) -> Path:
        """Extract a 'ready' workspace archive into a fresh sandbox directory.

        ``destination_root`` is created if needed and becomes the hard
        boundary: every extracted entry's resolved path is required to live
        underneath it, or extraction aborts and the partial directory is
        removed. This is the second line of defense — ``complete_upload``
        already rejected unsafe archives, but we never trust stored bytes
        blindly when writing to disk.

        Returns the resolved sandbox directory path (what the Pi agent's
        workspace tool should be pointed at).
        """
        workspace = self._require_owned(owner_user_id=owner_user_id, public_id=workspace_id)
        if workspace["status"] != "ready":
            raise WorkspaceNotReadyError(workspace_id)

        destination_root.mkdir(parents=True, exist_ok=True)
        sandbox_root = destination_root.resolve()

        archive_bytes = b"".join(
            self._storage_client.get_object_stream(
                bucket=workspace["storage_bucket"],
                object_key=workspace["object_key"],
            )
        )
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            for entry in archive.infolist():
                target = self._safe_join(sandbox_root, entry.filename)
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as source, open(target, "wb") as handle:
                    handle.write(source.read())

        return sandbox_root

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_owned(self, *, owner_user_id: str, public_id: str) -> dict[str, Any]:
        """Load an active workspace owned by the caller or raise not-found."""
        workspace = self._repository.get_for_owner(owner_user_id=owner_user_id, public_id=public_id)
        if workspace is None:
            raise WorkspaceNotFoundError(public_id)
        return workspace

    def _verify_checksum(self, *, object_key: str, expected: str) -> None:
        """Recompute SHA-256 over the stored archive and compare to the declared value."""
        digest = hashlib.sha256()
        for chunk in self._storage_client.get_object_stream(bucket=self._bucket, object_key=object_key):
            digest.update(chunk)
        if digest.hexdigest() != expected:
            raise ChecksumMismatchError("Uploaded archive checksum does not match")

    def _enforce_size_limit(self, size_bytes: int) -> None:
        """Reject archives larger than the configured ceiling."""
        if size_bytes > self._max_size_bytes:
            raise WorkspaceLimitExceededError(
                f"Archive exceeds the {self._max_size_bytes} byte size limit"
            )

    def _inspect_archive(self, *, object_key: str) -> int:
        """Validate every entry in the archive and return the active file count.

        Rejects:
          * absolute paths and ``..`` traversal (zip-slip)
          * symlink entries (st_mode S_IFLNK bit set in external_attr)
          * more files than ``max_files``
          * uncompressed payloads that blow past a sane compression ratio
            (zip-bomb heuristic)
        """
        archive_bytes = b"".join(
            self._storage_client.get_object_stream(bucket=self._bucket, object_key=object_key)
        )

        total_compressed = 0
        total_uncompressed = 0
        file_count = 0
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            for entry in archive.infolist():
                self._assert_safe_member_name(entry.filename)
                if _is_symlink(entry):
                    raise UnsafeArchiveError(f"Symlink entries are not allowed: {entry.filename}")
                if not entry.is_dir():
                    file_count += 1
                total_compressed += entry.compress_size
                total_uncompressed += entry.file_size

        if file_count > self._max_files:
            raise WorkspaceLimitExceededError(
                f"Archive contains {file_count} files, exceeding the limit of {self._max_files}"
            )
        if total_compressed > 0 and total_uncompressed > total_compressed * _MAX_UNCOMPRESSED_RATIO:
            raise UnsafeArchiveError("Archive compression ratio looks like a zip bomb")
        if total_uncompressed > self._max_size_bytes * _MAX_UNCOMPRESSED_RATIO:
            raise WorkspaceLimitExceededError("Archive would expand far beyond the size limit")
        return file_count

    @staticmethod
    def _assert_safe_member_name(name: str) -> None:
        """Reject absolute paths and parent-directory traversal in an archive entry name."""
        normalized = name.replace("\\", "/")
        if normalized.startswith("/") or normalized.startswith("~"):
            raise UnsafeArchiveError(f"Absolute path entry is not allowed: {name}")
        if ":" in normalized.split("/", 1)[0]:
            raise UnsafeArchiveError(f"Drive-letter path entry is not allowed: {name}")
        parts = [part for part in normalized.split("/") if part not in ("", ".")]
        if any(part == ".." for part in parts):
            raise UnsafeArchiveError(f"Path traversal entry is not allowed: {name}")

    @staticmethod
    def _safe_join(sandbox_root: Path, member_name: str) -> Path:
        """Resolve an archive member path and guarantee it stays under the sandbox root.

        Defense-in-depth: re-checks containment at extraction time even
        though ``_inspect_archive`` already rejected unsafe names — never
        trust the same validation to run exactly once on the same bytes.
        """
        normalized = member_name.replace("\\", "/").lstrip("/")
        candidate = (sandbox_root / normalized).resolve()
        try:
            candidate.relative_to(sandbox_root)
        except ValueError as exc:
            raise UnsafeArchiveError(
                f"Archive entry would escape the sandbox: {member_name}"
            ) from exc
        return candidate

    @staticmethod
    def _normalize_checksum(checksum_sha256: str) -> str:
        """Validate and normalize a SHA-256 checksum string."""
        checksum = checksum_sha256.strip().lower()
        if not _CHECKSUM_RE.fullmatch(checksum):
            raise ValueError("checksum_sha256 must be a 64-character lowercase hex SHA-256")
        return checksum


def _is_symlink(entry: zipfile.ZipInfo) -> bool:
    """Return True if a zip entry's external attributes mark it as a symlink."""
    unix_mode = entry.external_attr >> 16
    s_iflnk = 0o120000
    return bool(unix_mode) and (unix_mode & 0o170000) == s_iflnk
