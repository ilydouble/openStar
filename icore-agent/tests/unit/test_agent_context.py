"""Tests for agent context assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

import icore_agent.application.agent.context as app_context
import icore_agent.domain.agent.context as agent_context
from icore_agent.domain.agent.prompt import (
    assemble_prompt_envelope,
    build_base_instructions,
    build_context_items,
)
from icore_agent.domain.agent.session import (
    AgentMessageItem,
    ContextItem,
    UserInputType,
    UserMessageItem,
)
from icore_agent.domain.agent.tool import ToolChoice
from icore_agent.domain.files.models import FileAsset


def test_dedupe_file_uuids_preserves_first_seen_order() -> None:
    """File UUID normalization should keep the first occurrence of each UUID."""
    assert app_context.dedupe_file_uuids(
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


def test_turn_prompt_sources_are_assembled_into_context_items() -> None:
    """Prompt assembly rules should turn loaded sources into ContextItems."""
    sources = agent_context.TurnPromptSources(
        summary="Earlier summary",
        history_items=[],
        rag_context_items=[
            ContextItem(
                kind="rag_result",
                content="Retrieved policy details.",
            ),
        ],
        image_attachments=[
            agent_context.AgentImageAttachment(
                filename="chart.png",
                ref="https://files.example/img-1",
                file_uuid="img-1",
            ),
        ],
        file_attachments=[
            agent_context.AgentFileAttachment(
                filename="notes.txt",
                file_uuid="file-1",
            ),
        ],
        user_memory_prompt="User prefers concise Chinese replies.",
    )

    items = build_context_items(sources)

    assert [item.kind for item in items] == [
        "session_summary",
        "user_memory",
        "rag_result",
        "image_attachment",
        "file_attachment",
    ]
    assert all(isinstance(item, ContextItem) for item in items)
    assert items[0].content == "Earlier conversation summary:\nEarlier summary"
    assert items[1].content == "User prefers concise Chinese replies."
    assert items[2].content == "Retrieved policy details."
    assert 'filename="chart.png"' in items[3].content
    assert 'uuid="img-1"' in items[3].content
    assert 'ref="https://files.example/img-1"' in items[3].content
    assert 'filename="notes.txt"' in items[4].content
    assert 'uuid="file-1"' in items[4].content
    assert "Use read_uploaded_file" in items[4].content


def test_assemble_prompt_envelope_uses_image_inputs_when_main_model_supports_vision() -> None:
    """Vision-capable prompts should put image attachments on current user input."""
    sources = agent_context.TurnPromptSources(
        summary="Earlier summary",
        history_items=[],
        image_attachments=[
            agent_context.AgentImageAttachment(
                filename="chart.png",
                ref="https://files.example/img-1",
                file_uuid="img-1",
            ),
        ],
        file_attachments=[
            agent_context.AgentFileAttachment(
                filename="notes.txt",
                file_uuid="file-1",
            ),
        ],
    )

    envelope = assemble_prompt_envelope(
        base_instructions=build_base_instructions(),
        sources=sources,
        user_text="Summarize the attachment",
        tools=[],
        tool_choice=ToolChoice.AUTO,
        include_image_inputs=True,
    )

    assert [item.kind for item in envelope.context_items] == [
        "session_summary",
        "file_attachment",
    ]
    assert [block.type for block in envelope.current_user_item.content] == [
        UserInputType.TEXT.value,
        UserInputType.TEXT.value,
        UserInputType.IMAGE.value,
    ]
    assert envelope.current_user_item.content[1].text == (
        'Attached image available to the model: filename="chart.png" uuid="img-1"'
    )
    assert envelope.current_user_item.content[2].image_file_uuid == "img-1"
    assert envelope.current_user_item.content[2].image_url == "https://files.example/img-1"


def test_assemble_prompt_envelope_keeps_image_refs_as_context_without_vision() -> None:
    """Non-vision prompts should leave images as metadata-only context refs."""
    sources = agent_context.TurnPromptSources(
        summary=None,
        history_items=[],
        image_attachments=[
            agent_context.AgentImageAttachment(
                filename="chart.png",
                ref="https://files.example/img-1",
                file_uuid="img-1",
            ),
        ],
        file_attachments=[],
    )

    envelope = assemble_prompt_envelope(
        base_instructions="Base policy",
        sources=sources,
        user_text="What is in this image?",
        tools=[],
        include_image_inputs=False,
    )

    assert [item.kind for item in envelope.context_items] == [
        "image_attachment",
    ]
    assert [block.type for block in envelope.current_user_item.content] == [
        UserInputType.TEXT.value,
    ]


@pytest.mark.asyncio
async def test_load_turn_prompt_sources_prefers_cached_history() -> None:
    """Cached conversation history should be converted to model-visible items."""
    sources = await app_context.load_turn_prompt_sources(
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

    assert sources.summary == "Earlier summary"
    assert _history_texts(sources.history_items) == [
        ("user", "Cached question")]


@pytest.mark.asyncio
async def test_load_turn_prompt_sources_falls_back_to_persisted_history_when_not_incognito() -> None:
    """Persisted chat messages should be used when Redis has no recent messages."""
    history = FakeHistory([
        {"role": "assistant", "content": "Persisted answer"},
    ])

    sources = await app_context.load_turn_prompt_sources(
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
    assert _history_texts(sources.history_items) == [
        ("assistant", "Persisted answer"),
    ]


@pytest.mark.asyncio
async def test_load_turn_prompt_sources_excludes_current_user_message_from_fallback_history() -> None:
    """Durable fallback history should not duplicate the current turn prompt."""
    history = FakeHistory([
        {"role": "assistant", "content": "Persisted answer"},
        {"role": "user", "content": "Hello"},
    ])

    sources = await app_context.load_turn_prompt_sources(
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

    assert _history_texts(sources.history_items) == [
        ("assistant", "Persisted answer"),
    ]


@pytest.mark.asyncio
async def test_load_turn_prompt_sources_skips_history_fallback_and_memory_prompt_in_incognito() -> None:
    """Incognito context should not load persisted history or durable memory."""
    history = FakeHistory([
        {"role": "assistant", "content": "Persisted answer"},
    ])
    memory_service = FakeUserMemoryService("remember this")

    sources = await app_context.load_turn_prompt_sources(
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
    assert sources.user_memory_prompt is None


@pytest.mark.asyncio
async def test_load_turn_prompt_sources_buckets_image_and_file_attachments() -> None:
    """File UUIDs should resolve into metadata-only attachment refs."""
    assets = {
        "txt-1": _asset("txt-1", "notes.txt", "text/plain"),
        "img-1": _asset("img-1", "chart.png", "image/png"),
        "csv-1": _asset("csv-1", "data.csv", "text/csv"),
        "pdf-1": _asset("pdf-1", "paper.pdf", "application/pdf"),
    }
    file_service = FakeFileService(assets)

    sources = await app_context.load_turn_prompt_sources(
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

    context_items = build_context_items(sources)
    assert [item.kind for item in context_items] == [
        "user_memory",
        "image_attachment",
        "file_attachment",
        "file_attachment",
        "file_attachment",
    ]
    assert 'filename="chart.png"' in context_items[1].content
    assert 'uuid="img-1"' in context_items[1].content
    assert 'ref="https://files.example/img-1"' in context_items[1].content
    assert 'filename="notes.txt"' in context_items[2].content
    assert 'uuid="txt-1"' in context_items[2].content
    assert 'filename="data.csv"' in context_items[3].content
    assert 'filename="paper.pdf"' in context_items[4].content
    assert sources.user_memory_prompt == "memory prompt"
    assert file_service.read_calls == []
    assert file_service.materialize_calls == []


@pytest.mark.asyncio
async def test_load_turn_prompt_sources_returns_empty_sources_when_cache_load_fails() -> None:
    """Conversation cache failures should leave the turn runnable with no context."""
    sources = await app_context.load_turn_prompt_sources(
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

    assert sources == agent_context.TurnPromptSources.empty()


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
