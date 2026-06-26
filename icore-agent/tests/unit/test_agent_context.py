"""Tests for agent context assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

import icore_agent.application.agent.context as agent_context
from icore_agent.domain.agent.session import AgentMessageItem, UserMessageItem
from icore_agent.domain.files.models import FileAsset


def test_dedupe_file_uuids_preserves_first_seen_order() -> None:
    """File UUID normalization should keep the first occurrence of each UUID."""
    assert agent_context.dedupe_file_uuids(
        (" a ", "b", "a", "", "b")) == ("a", "b")


def _history_texts(items: list[UserMessageItem | AgentMessageItem]) -> list[tuple[str, str]]:
    """Return role/text pairs from provider-neutral session history items."""
    pairs: list[tuple[str, str]] = []
    for item in items:
        if isinstance(item, UserMessageItem):
            pairs.append(("user", item.content[0].text or ""))
        else:
            pairs.append(("assistant", item.text))
    return pairs


@pytest.mark.asyncio
async def test_load_agent_context_prefers_cached_history() -> None:
    """Cached conversation history should be converted to model-visible items."""
    context = await agent_context.load_agent_context(
        session_id="session-1",
        file_uuids=(),
        user_id="user-1",
        user_message="Hello",
        incognito=False,
        file_service=FakeFileService({}),
        agent_session=FakeHistory([
            {"role": "user", "content": "Persisted question"},
        ]),
        conversation_memory=FakeMemory(
            summary="Earlier summary",
            messages=[{"role": "user", "content": "Cached question"}],
        ),
        user_memory_service=None,
    )

    assert context.summary == "Earlier summary"
    assert _history_texts(context.history_items) == [
        ("user", "Cached question")]


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
        agent_session=history,
        conversation_memory=FakeMemory(summary=None, messages=[]),
        user_memory_service=None,
    )

    assert history.load_calls == [("session-1", "user-1")]
    assert _history_texts(context.history_items) == [
        ("assistant", "Persisted answer"),
    ]


@pytest.mark.asyncio
async def test_load_agent_context_excludes_current_user_message_from_fallback_history() -> None:
    """Durable fallback history should not duplicate the current turn prompt."""
    history = FakeHistory([
        {"role": "assistant", "content": "Persisted answer"},
        {"role": "user", "content": "Hello"},
    ])

    context = await agent_context.load_agent_context(
        session_id="session-1",
        file_uuids=(),
        user_id="user-1",
        user_message="Hello",
        incognito=False,
        file_service=FakeFileService({}),
        agent_session=history,
        conversation_memory=FakeMemory(summary=None, messages=[]),
        user_memory_service=None,
    )

    assert _history_texts(context.history_items) == [
        ("assistant", "Persisted answer"),
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
        agent_session=history,
        conversation_memory=FakeMemory(summary=None, messages=[]),
        user_memory_service=memory_service,
    )

    assert history.load_calls == []
    assert memory_service.build_calls == []
    assert context.user_memory_prompt is None


@pytest.mark.asyncio
async def test_load_agent_context_buckets_image_and_file_attachments() -> None:
    """File UUIDs should resolve into metadata-only attachment refs."""
    assets = {
        "txt-1": _asset("txt-1", "notes.txt", "text/plain"),
        "img-1": _asset("img-1", "chart.png", "image/png"),
        "csv-1": _asset("csv-1", "data.csv", "text/csv"),
        "pdf-1": _asset("pdf-1", "paper.pdf", "application/pdf"),
    }
    file_service = FakeFileService(assets)

    context = await agent_context.load_agent_context(
        session_id="session-1",
        file_uuids=("txt-1", "img-1", "csv-1", "pdf-1", "txt-1"),
        user_id="user-1",
        user_message="Use these files",
        incognito=False,
        file_service=file_service,
        agent_session=FakeHistory([]),
        conversation_memory=FakeMemory(summary=None, messages=[]),
        user_memory_service=FakeUserMemoryService("memory prompt"),
    )

    assert context.image_attachment_payloads == [
        {
            "filename": "chart.png",
            "ref": "https://files.example/img-1",
            "file_uuid": "img-1",
        }
    ]
    assert context.file_attachment_payloads == [
        {"filename": "notes.txt", "file_uuid": "txt-1"},
        {"filename": "data.csv", "file_uuid": "csv-1"},
        {"filename": "paper.pdf", "file_uuid": "pdf-1"},
    ]
    assert context.user_memory_prompt == "memory prompt"
    assert file_service.read_calls == []
    assert file_service.materialize_calls == []


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
        agent_session=FakeHistory([{"role": "user", "content": "Persisted"}]),
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
    ) -> None:
        """Create the fake with owned assets."""
        self.assets = assets
        self.read_calls: list[tuple[str, str]] = []
        self.materialize_calls: list[tuple[str, str]] = []

    def get_owned_asset(self, *, uploader_public_id: str, file_uuid: str) -> FileAsset:
        """Return an owned file asset."""
        return self.assets[file_uuid]

    def create_download_url(self, *, uploader_public_id: str, file_uuid: str) -> str:
        """Return a deterministic download URL."""
        return f"https://files.example/{file_uuid}"

    def read_file_bytes(self, *, uploader_public_id: str, file_uuid: str) -> bytes:
        """Fail if context loading tries to read file bytes."""
        self.read_calls.append((uploader_public_id, file_uuid))
        raise AssertionError("context must not read uploaded file bytes")

    def materialize_temp_file(self, *, uploader_public_id: str, file_uuid: str):
        """Fail if context loading tries to materialize uploaded files."""
        self.materialize_calls.append((uploader_public_id, file_uuid))
        raise AssertionError("context must not materialize uploaded files")


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
