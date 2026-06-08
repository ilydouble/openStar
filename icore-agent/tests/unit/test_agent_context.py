"""Tests for agent context assembly."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import icore_agent.application.agent.context as agent_context
from icore_agent.domain.files.models import FileAsset


def test_dedupe_file_uuids_preserves_first_seen_order() -> None:
    """File UUID normalization should keep the first occurrence of each UUID."""
    assert agent_context.dedupe_file_uuids(
        (" a ", "b", "a", "", "b")) == ("a", "b")


@pytest.mark.asyncio
async def test_load_agent_context_prefers_cached_history() -> None:
    """Cached conversation history should be converted to Strands messages."""
    context = await agent_context.load_agent_context(
        session_id="session-1",
        file_uuids=(),
        user_id="user-1",
        user_message="Hello",
        incognito=False,
        file_service=FakeFileService({}),
        chat_history=FakeHistory([
            {"role": "user", "content": "Persisted question"},
        ]),
        conversation_memory=FakeMemory(
            summary="Earlier summary",
            messages=[{"role": "user", "content": "Cached question"}],
        ),
        user_memory_service=None,
    )

    assert context.summary == "Earlier summary"
    assert context.strands_history == [
        {"role": "user", "content": [
            {"type": "text", "text": "Cached question"}]},
    ]


@pytest.mark.asyncio
async def test_load_agent_context_falls_back_to_persisted_history_when_not_incognito() -> None:
    """Persisted chat messages should be used when Redis has no recent messages."""
    history = FakeHistory([
        {"role": "assistant", "content": "Persisted answer"},
    ])

    context = await agent_context.load_agent_context(
        session_id="session-1",
        file_uuids=(),
        user_id="user-1",
        user_message="Hello",
        incognito=False,
        file_service=FakeFileService({}),
        chat_history=history,
        conversation_memory=FakeMemory(summary=None, messages=[]),
        user_memory_service=None,
    )

    assert history.load_calls == [("session-1", "user-1")]
    assert context.strands_history == [
        {"role": "assistant", "content": [
            {"type": "text", "text": "Persisted answer"}]},
    ]


@pytest.mark.asyncio
async def test_load_agent_context_skips_history_fallback_and_memory_prompt_in_incognito() -> None:
    """Incognito context should not load persisted history or durable memory."""
    history = FakeHistory([
        {"role": "assistant", "content": "Persisted answer"},
    ])
    memory_service = FakeUserMemoryService("remember this")

    context = await agent_context.load_agent_context(
        session_id="session-1",
        file_uuids=(),
        user_id="user-1",
        user_message="Hello",
        incognito=True,
        file_service=FakeFileService({}),
        chat_history=history,
        conversation_memory=FakeMemory(summary=None, messages=[]),
        user_memory_service=memory_service,
    )

    assert history.load_calls == []
    assert memory_service.build_calls == []
    assert context.user_memory_prompt is None


@pytest.mark.asyncio
async def test_load_agent_context_buckets_text_image_and_data_attachments(tmp_path: Path) -> None:
    """File UUIDs should resolve into text, image, and structured data context."""
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("name,value\nalpha,1\nbeta,2\n", encoding="utf-8")
    assets = {
        "txt-1": _asset("txt-1", "notes.txt", "text/plain"),
        "img-1": _asset("img-1", "chart.png", "image/png"),
        "csv-1": _asset("csv-1", "data.csv", "text/csv"),
    }
    file_service = FakeFileService(
        assets,
        bytes_by_uuid={"txt-1": b"plain notes"},
        temp_files={"csv-1": csv_path},
    )

    context = await agent_context.load_agent_context(
        session_id="session-1",
        file_uuids=("txt-1", "img-1", "csv-1", "txt-1"),
        user_id="user-1",
        user_message="Use these files",
        incognito=False,
        file_service=file_service,
        chat_history=FakeHistory([]),
        conversation_memory=FakeMemory(summary=None, messages=[]),
        user_memory_service=FakeUserMemoryService("memory prompt"),
    )

    assert "### notes.txt (txt-1)\n\nplain notes" == context.attachments_text
    assert context.image_attachment_payloads == [
        {
            "filename": "chart.png",
            "ref": "https://files.example/img-1",
            "file_uuid": "img-1",
        }
    ]
    assert context.data_attachment_payloads[0]["filename"] == "data.csv"
    assert context.data_attachment_payloads[0]["row_count"] == 2
    assert [
        column["name"]
        for column in context.data_attachment_payloads[0]["columns"]
    ] == ["name", "value"]
    assert context.user_memory_prompt == "memory prompt"


@pytest.mark.asyncio
async def test_load_agent_context_returns_empty_context_when_cache_load_fails() -> None:
    """Conversation cache failures should leave the turn runnable with no context."""
    context = await agent_context.load_agent_context(
        session_id="session-1",
        file_uuids=("txt-1",),
        user_id="user-1",
        user_message="Hello",
        incognito=False,
        file_service=FakeFileService({
            "txt-1": _asset("txt-1", "notes.txt", "text/plain"),
        }),
        chat_history=FakeHistory([{"role": "user", "content": "Persisted"}]),
        conversation_memory=FakeMemory(raise_on_get=True),
        user_memory_service=FakeUserMemoryService("memory prompt"),
    )

    assert context == agent_context.AgentContext.empty()


@dataclass(frozen=True)
class FakeMemory:
    """Conversation memory fake for context loader tests."""

    summary: str | None = None
    messages: list[dict[str, Any]] | None = None
    raise_on_get: bool = False

    async def get_context(self, session_id: str) -> tuple[str | None, list[dict[str, Any]]]:
        """Return the configured conversation snapshot."""
        if self.raise_on_get:
            raise RuntimeError("redis unavailable")
        return self.summary, list(self.messages or [])

    async def append_message(self, session_id: str, role: str, content: str) -> bool:
        """Accept appends to satisfy the protocol."""
        return False


class FakeHistory:
    """Chat history fake for context loader tests."""

    def __init__(self, messages: list[dict[str, Any]]) -> None:
        """Create the fake with persisted messages."""
        self.messages = messages
        self.load_calls: list[tuple[str, str]] = []

    def load_messages(self, public_id: str, user_id: str) -> list[dict[str, Any]]:
        """Return configured persisted history."""
        self.load_calls.append((public_id, user_id))
        return list(self.messages)


class FakeUserMemoryService:
    """User memory fake for context loader tests."""

    def __init__(self, prompt: str | None) -> None:
        """Create the fake with a prompt return value."""
        self.prompt = prompt
        self.build_calls: list[tuple[str, Any]] = []

    def build_memory_prompt(self, user_id: str, turn: Any) -> str | None:
        """Record prompt construction inputs."""
        self.build_calls.append((user_id, turn))
        return self.prompt


class FakeFileService:
    """File service fake for context loader tests."""

    def __init__(
        self,
        assets: dict[str, FileAsset],
        *,
        bytes_by_uuid: dict[str, bytes] | None = None,
        temp_files: dict[str, Path] | None = None,
    ) -> None:
        """Create the fake with owned assets and optional file contents."""
        self.assets = assets
        self.bytes_by_uuid = bytes_by_uuid or {}
        self.temp_files = temp_files or {}

    def get_owned_asset(self, *, uploader_public_id: str, file_uuid: str) -> FileAsset:
        """Return an owned file asset."""
        return self.assets[file_uuid]

    def create_download_url(self, *, uploader_public_id: str, file_uuid: str) -> str:
        """Return a deterministic download URL."""
        return f"https://files.example/{file_uuid}"

    def read_file_bytes(self, *, uploader_public_id: str, file_uuid: str) -> bytes:
        """Return configured file bytes."""
        return self.bytes_by_uuid[file_uuid]

    def materialize_temp_file(self, *, uploader_public_id: str, file_uuid: str) -> tuple[FileAsset, Path]:
        """Return a configured local temporary file path."""
        return self.assets[file_uuid], self.temp_files[file_uuid]


def _asset(file_uuid: str, filename: str, content_type: str) -> FileAsset:
    """Build a completed file asset for context tests."""
    return FileAsset(
        file_uuid=file_uuid,
        original_filename=filename,
        uploader_public_id="user-1",
        uploaded_at=None,
        deleted_at=None,
        storage_bucket="icore-files",
        object_key=f"files/user-1/{file_uuid}",
        storage_etag="etag",
        content_type=content_type,
        checksum_sha256="a" * 64,
    )
