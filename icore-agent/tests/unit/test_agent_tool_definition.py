"""Tests for structured agent tool definitions."""

from __future__ import annotations

from datetime import UTC, datetime
from icore_agent.application.agent.tool.catalog import (
    build_orchestrator_tool_definitions,
)
from icore_agent.domain.agent.tool import (
    ToolExecutionContext,
)
from icore_agent.domain.files.models import FileAsset


def test_read_uploaded_file_definition_reads_owned_asset_by_uuid() -> None:
    """Tool catalog should expose uploaded file reads through scoped UUID access."""
    file_service = FakeUploadedFileService({
        "file-1": _asset("file-1", "notes.txt", "text/plain"),
    }, {"file-1": b"plain notes"})
    definitions = build_orchestrator_tool_definitions(
        session_id="session-1",
        user_id="user-1",
        file_service=file_service,
    )

    definition = next(
        item for item in definitions if item.name == "read_uploaded_file"
    )
    result = definition.execute(
        "call-1",
        {"file_uuid": "file-1"},
        ToolExecutionContext(tool_call_id="call-1"),
    )

    assert definition.prompt_snippet
    assert 'uploaded_file filename="notes.txt" uuid="file-1"' in result
    assert "plain notes" in result
    assert file_service.calls == [
        ("get", "user-1", "file-1"),
        ("read", "user-1", "file-1"),
    ]


def test_read_uploaded_file_definition_reports_missing_service() -> None:
    """Tool should fail readably when uploaded file access is not wired."""
    definitions = build_orchestrator_tool_definitions(session_id="session-1")
    definition = next(
        item for item in definitions if item.name == "read_uploaded_file"
    )

    result = definition.execute(
        "call-1",
        {"file_uuid": "file-1"},
        ToolExecutionContext(tool_call_id="call-1"),
    )

    assert result == "[UNAVAILABLE] Uploaded file access is not configured."


class FakeUploadedFileService:
    """Uploaded file service fake for tool catalog tests."""

    def __init__(
        self,
        assets: dict[str, FileAsset],
        bytes_by_uuid: dict[str, bytes],
    ) -> None:
        """Create the fake with assets and bytes."""
        self.assets = assets
        self.bytes_by_uuid = bytes_by_uuid
        self.calls: list[tuple[str, str, str]] = []

    def get_owned_asset(self, *, uploader_public_id: str, file_uuid: str) -> FileAsset:
        """Return the configured asset."""
        self.calls.append(("get", uploader_public_id, file_uuid))
        return self.assets[file_uuid]

    def read_file_bytes(self, *, uploader_public_id: str, file_uuid: str) -> bytes:
        """Return configured file bytes."""
        self.calls.append(("read", uploader_public_id, file_uuid))
        return self.bytes_by_uuid[file_uuid]


def _asset(file_uuid: str, filename: str, content_type: str) -> FileAsset:
    """Build a completed file asset for tool tests."""
    return FileAsset(
        file_uuid=file_uuid,
        original_filename=filename,
        uploader_public_id="user-1",
        uploaded_at=datetime.now(UTC),
        deleted_at=None,
        storage_bucket="icore-files",
        object_key=f"files/user-1/{file_uuid}",
        storage_etag="etag",
        content_type=content_type,
        checksum_sha256="a" * 64,
    )
