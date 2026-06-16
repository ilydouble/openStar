"""Tests for structured agent tool definitions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from icore_agent.application.agent.tool.catalog import (
    build_orchestrator_tool_definitions,
)
from icore_agent.application.agent.tool import (
    ToolDefinition,
    ToolExecutionContext,
)
from icore_agent.domain.files.models import FileAsset
from icore_agent.infrastructure.agent.strands import AgentTool


@pytest.mark.asyncio
async def test_agent_tool_exposes_spec_and_streams_success() -> None:
    """AgentTool should adapt ToolDefinition into a Strands tool result."""
    calls: list[tuple[str, dict[str, Any], ToolExecutionContext]] = []

    def _execute(
        tool_call_id: str,
        params: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        """Record invocation details and return structured data."""
        calls.append((tool_call_id, params, context))
        return {"echo": params["value"]}

    tool = AgentTool(ToolDefinition(
        name="echo_tool",
        label="Echo tool",
        description="Echo a value.",
        parameters={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
        execute=_execute,
        prompt_snippet="Echo a value.",
    ))

    events = []
    async for event in tool.stream(
        {"toolUseId": "call-1", "name": "echo_tool", "input": {"value": "ok"}},
        {"session_id": "session-1"},
    ):
        events.append(event)

    assert tool.tool_name == "echo_tool"
    assert tool.tool_type == "python"
    assert tool.tool_spec["name"] == "echo_tool"
    assert tool.tool_spec["inputSchema"]["json"]["required"] == ["value"]
    assert calls[0][0] == "call-1"
    assert calls[0][1] == {"value": "ok"}
    assert calls[0][2].invocation_state["session_id"] == "session-1"
    assert events == [{
        "toolUseId": "call-1",
        "status": "success",
        "content": [{"text": '{"echo": "ok"}'}],
    }]


@pytest.mark.asyncio
async def test_agent_tool_streams_error_result_on_exception() -> None:
    """AgentTool should convert executor exceptions into error results."""

    def _execute(
        _tool_call_id: str,
        _params: dict[str, Any],
        _context: ToolExecutionContext,
    ) -> str:
        """Raise a stable test exception."""
        raise RuntimeError("boom")

    tool = AgentTool(ToolDefinition(
        name="failing_tool",
        label="Failing tool",
        description="Always fails.",
        parameters={"type": "object"},
        execute=_execute,
    ))

    events = []
    async for event in tool.stream(
        {"toolUseId": "call-2", "name": "failing_tool", "input": {}},
        {},
    ):
        events.append(event)

    assert events == [{
        "toolUseId": "call-2",
        "status": "error",
        "content": [{"text": "boom"}],
    }]


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
