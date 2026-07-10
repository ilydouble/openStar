"""Tests for agent turn application services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from icore_agent.contexts.account.domain.user import AuthenticatedUser
from icore_agent.contexts.agent.application import (
    AgentIntent,
    AgentTurnService,
    classify_turn_intent,
)
from icore_agent.contexts.agent.application.context import dedupe_file_uuids
from icore_agent.contexts.agent.domain.loop import ModelStepResult
from icore_agent.contexts.agent.domain.prompt import PromptEnvelope
from icore_agent.contexts.agent.domain.session import (
    AgentMessageItem,
    SessionItem,
    ToolCallItem,
    ToolFunction,
    UserMessageItem,
)
from icore_agent.contexts.agent.domain.turn import (
    AgentTurnCommand,
    Turn,
    TurnEventKind,
    TurnStatus,
)
from icore_agent.contexts.files.domain.models import FileAsset


def test_classify_turn_intent_classifies_task_keywords() -> None:
    """Intent classification should tag task-like messages for turn metadata."""
    intent = classify_turn_intent("帮我搜索今天的 AI 新闻")

    assert intent is AgentIntent.TASK


def test_dedupe_file_uuids_preserves_first_seen_order() -> None:
    """File UUID metadata should be deduplicated before message persistence."""
    assert dedupe_file_uuids((" a ", "b", "a", "", "b")) == ("a", "b")


@pytest.mark.asyncio
async def test_agent_turn_run_persists_canonical_turn_items_and_invokes_model_client() -> None:
    """Non-streaming turns should write canonical turn/session-item state only."""
    history = FakeHistory()
    memory = FakeMemory()
    factory = FakeModelClientFactory(reply="assistant reply")
    usage = FakeUsageService()
    service = AgentTurnService(
        agent_session=history,
        file_service=FakeFileService(),
        conversation_memory=memory,
        model_client_factory=factory,
        usage_service=usage,
    )

    turn = await service.run(_command(stream=False, file_uuids=("f1", "f1")))

    assert isinstance(turn, Turn)
    assert turn.session_id == "session-1"
    assert turn.status is TurnStatus.COMPLETED
    assert turn.reply_text() == "assistant reply"
    assert history.calls[0] == ("ensure", "session-1", "user-1", "Hello")
    assert history.calls[1][0:4] == (
        "start-turn", "session-1", "user-1", "Hello")
    assert history.calls[1][4] == "Hello"
    assert history.calls[1][5] == {"file_uuids": ["f1"]}
    assert ("load", "session-1", "user-1") in history.calls
    upserted_types = [
        call[3]
        for call in history.calls
        if call[0] == "upsert"
    ]
    assert "context" in upserted_types
    assert upserted_types.count("agent_message") == 2
    assert all(call[0] not in {"user", "assistant", "tool-link"}
               for call in history.calls)
    completed_call = next(
        call for call in history.calls if call[0] == "complete")
    assert completed_call[4] == TurnStatus.COMPLETED
    assert completed_call[8]["total_tokens"] > 0
    assert memory.appended == [
        ("session-1", "user", "Hello"),
        ("session-1", "assistant", "assistant reply"),
    ]
    assert "enable_tools" not in factory.calls[0]
    assert "agent_hint" not in factory.calls[0]
    assert "hooks" not in factory.calls[0]
    assert "prompt_envelope" not in factory.calls[0]
    assert "tool_definitions" not in factory.calls[0]
    assert factory.client.prompt_envelopes
    assert usage.calls == [
        ("user-1", "attachments", 1),
        ("user-1", "tasks", 1),
    ]
    assert len(usage.llm_calls) == 1
    assert usage.llm_calls[0]["user_id"] == "user-1"
    assert usage.llm_calls[0]["total_tokens"] > 0


@pytest.mark.asyncio
async def test_agent_turn_run_persists_tool_calls_as_session_items() -> None:
    """Completed turns should store tool calls as canonical ToolCallItem payloads."""
    history = FakeHistory()
    service = AgentTurnService(
        agent_session=history,
        file_service=FakeFileService(),
        conversation_memory=FakeMemory(),
        model_client_factory=FakeModelClientFactory(
            reply="assistant reply",
            emit_tool_call=True,
        ),
        usage_service=FakeUsageService(),
    )

    turn = await service.run(_command(stream=False))

    assert turn.reply_text() == "assistant reply"
    tool_items = [
        call[4]
        for call in history.calls
        if call[0] == "upsert" and call[3] == "tool_call"
    ]
    assert [item.provider_tool_call_id for item in tool_items] == [
        "tool-1",
        "tool-1",
    ]
    agent_items = [
        call[4]
        for call in history.calls
        if call[0] == "upsert" and call[3] == "agent_message"
    ]
    assert len({item.id for item in agent_items}) == 1
    assert agent_items[-1].text == "assistant reply"
    assert '"comparison": "greater_than"' in tool_items[-1].result.content
    assert tool_items[-1].result.structured_content is None
    assert all(call[0] != "tool-link" for call in history.calls)


@pytest.mark.asyncio
async def test_agent_turn_run_skips_user_memory_without_compression() -> None:
    """Normal turns should not trigger durable memory extraction."""
    memory_service = TrackingUserMemoryService()
    service = AgentTurnService(
        agent_session=FakeHistory(),
        file_service=FakeFileService(),
        conversation_memory=FakeMemory(),
        model_client_factory=FakeModelClientFactory(reply="assistant reply"),
        usage_service=FakeUsageService(),
        user_memory_service=memory_service,
    )

    await service.run(_command(stream=False))

    assert memory_service.compression_checks == [False]
    assert memory_service.extract_calls == []


@pytest.mark.asyncio
async def test_agent_turn_run_schedules_user_memory_extract_on_compression() -> None:
    """Redis compression during a turn should trigger durable memory extraction."""
    memory_service = TrackingUserMemoryService()
    conversation_memory = FakeMemory(compress_on_append=True)
    service = AgentTurnService(
        agent_session=FakeHistory(),
        file_service=FakeFileService(),
        conversation_memory=conversation_memory,
        model_client_factory=FakeModelClientFactory(reply="assistant reply"),
        usage_service=FakeUsageService(),
        user_memory_service=memory_service,
    )

    await service.run(_command(stream=False))

    assert memory_service.compression_checks == [True]
    assert len(memory_service.extract_calls) == 1
    assert memory_service.extract_calls[0]["user_id"] == "user-1"
    assert memory_service.extract_calls[0]["session_id"] == "session-1"


@pytest.mark.asyncio
async def test_agent_turn_stream_skips_user_memory_without_compression() -> None:
    """Streaming turns should not extract durable memory unless compressed."""
    memory_service = TrackingUserMemoryService()
    service = AgentTurnService(
        agent_session=FakeHistory(),
        file_service=FakeFileService(),
        conversation_memory=FakeMemory(),
        model_client_factory=FakeModelClientFactory(reply="", streaming=True),
        usage_service=FakeUsageService(),
        user_memory_service=memory_service,
    )

    event_stream = await service.stream(_command(stream=True))
    async for event in event_stream:
        if event.kind is TurnEventKind.TURN_COMPLETED:
            break

    assert memory_service.compression_checks == [False]
    assert memory_service.extract_calls == []


@pytest.mark.asyncio
async def test_agent_turn_stream_emits_status_tokens_and_done() -> None:
    """Streaming agent turns should expose typed application events."""
    history = FakeHistory()
    memory = FakeMemory()
    factory = FakeModelClientFactory(reply="", streaming=True)
    service = AgentTurnService(
        agent_session=history,
        file_service=FakeFileService(),
        conversation_memory=memory,
        model_client_factory=factory,
        usage_service=FakeUsageService(),
    )

    event_stream = await service.stream(_command(stream=True, file_uuids=("f1",)))
    events = []
    async for event in event_stream:
        events.append(event)
        if event.kind is TurnEventKind.TURN_COMPLETED:
            break

    assert [event.kind for event in events] == [
        TurnEventKind.TURN_STARTED,
        TurnEventKind.ITEM_COMPLETED,
        TurnEventKind.ITEM_COMPLETED,
        TurnEventKind.ITEM_STARTED,
        TurnEventKind.ITEM_DELTA,
        TurnEventKind.ITEM_COMPLETED,
        TurnEventKind.TURN_COMPLETED,
    ]
    assert any(
        event.item is not None and event.item.type == "context"
        for event in events
    )
    assert "".join(
        event.delta["text_append"]
        for event in events
        if event.kind is TurnEventKind.ITEM_DELTA
    ) == "Hi"
    assert all(event.seq is not None for event in events)
    assert all(event.run_id for event in events)
    assert len({
        event.event_id
        for event in events
    }) == len(events)
    assert any(
        call[0] == "upsert"
        and call[3] == "agent_message"
        and call[4].text == "Hi"
        for call in history.calls
    )
    event_calls = [call for call in history.calls if call[0] == "append-event"]
    assert [call[4] for call in event_calls] == [
        event.kind.value for event in events
    ]


@pytest.mark.asyncio
async def test_agent_turn_run_incognito_skips_history_and_memory_extract() -> None:
    """Incognito turns should skip PostgreSQL persistence and memory extraction."""
    history = FakeHistory()
    memory_service = TrackingUserMemoryService()
    conversation_memory = FakeMemory(compress_on_append=True)
    factory = FakeModelClientFactory(reply="assistant reply")
    service = AgentTurnService(
        agent_session=history,
        file_service=FakeFileService(),
        conversation_memory=conversation_memory,
        model_client_factory=factory,
        usage_service=FakeUsageService(),
        user_memory_service=memory_service,
    )

    await service.run(_command(stream=False, incognito=True))

    assert history.calls == []
    assert conversation_memory.appended == [
        ("session-1", "user", "Hello"),
        ("session-1", "assistant", "assistant reply"),
    ]
    assert memory_service.compression_checks == []
    assert memory_service.extract_calls == []
    assert all(
        item.kind != "user_memory"
        for item in factory.client.prompt_envelopes[0].context_items
    )


@pytest.mark.asyncio
async def test_agent_turn_run_incognito_skips_memory_prompt_injection() -> None:
    """Incognito turns should not inject durable user memory into the prompt."""
    memory_service = TrackingUserMemoryService()

    def _build_prompt(user_id: str, turn: Any) -> str:
        memory_service.build_calls.append((user_id, turn))
        return "remember this"

    memory_service.build_calls = []
    # type: ignore[method-assign]
    memory_service.build_memory_prompt = _build_prompt
    factory = FakeModelClientFactory(reply="assistant reply")
    service = AgentTurnService(
        agent_session=FakeHistory(),
        file_service=FakeFileService(),
        conversation_memory=FakeMemory(),
        model_client_factory=factory,
        usage_service=FakeUsageService(),
        user_memory_service=memory_service,
    )

    await service.run(_command(stream=False, incognito=True))

    assert memory_service.build_calls == []
    assert all(
        item.kind != "user_memory"
        for item in factory.client.prompt_envelopes[0].context_items
    )


def _command(
    *,
    stream: bool,
    file_uuids: tuple[str, ...] = (),
    incognito: bool = False,
) -> AgentTurnCommand:
    """Build one agent command for tests."""
    return AgentTurnCommand(
        message="Hello",
        session_id="session-1",
        stream=stream,
        tenant_code="",
        file_uuids=file_uuids,
        display_caption=None,
        agent_message=None,
        template_id=None,
        incognito=incognito,
        user=_auth_user(),
    )


def _auth_user() -> AuthenticatedUser:
    """Build the authenticated domain user used by agent command tests."""
    return AuthenticatedUser(
        public_id="user-1",
        email="user@example.com",
        name="User One",
        roles=("owner",),
    )


class FakeUsageService:
    """Usage service fake that records quota consumption calls."""

    def __init__(self) -> None:
        """Create the fake usage service."""
        self.calls: list[tuple[str, str, int]] = []
        self.llm_calls: list[dict[str, Any]] = []

    def consume_quota(self, user_id: str, resource: str, amount: int = 1) -> None:
        """Record one quota consumption call."""
        self.calls.append((user_id, resource, amount))

    def consume_task(self, user_id: str) -> None:
        """Record one completed task quota consumption call."""
        self.calls.append((user_id, "tasks", 1))

    def check_quota(
        self,
        user_id: str,
        resource: str,
        amount: int = 1,
    ) -> tuple[bool, str | None]:
        """Allow quota checks during chat turn tests."""
        return True, None

    def record_llm_usage(self, **payload: Any) -> None:
        """Record one LLM usage persistence call."""
        self.llm_calls.append(dict(payload))


class FakeMemory:
    """In-memory conversation cache fake."""

    def __init__(self, *, compress_on_append: bool = False) -> None:
        """Create the fake memory store."""
        self.compress_on_append = compress_on_append
        self.appended: list[tuple[str, str, str]] = []

    async def get_context(self, session_id: str) -> tuple[str | None, list[dict]]:
        """Return an empty cached conversation."""
        return None, []

    async def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> bool:
        """Record one appended cached message."""
        self.appended.append((session_id, role, content))
        return self.compress_on_append


class FakeHistory:
    """Chat history service fake."""

    def __init__(self) -> None:
        """Create the fake history store."""
        self.calls: list[tuple] = []

    def ensure_owned_session(
        self,
        public_id: str,
        user_id: str,
        *,
        title: str = "",
    ) -> None:
        """Record session ownership setup."""
        self.calls.append(("ensure", public_id, user_id, title))

    def start_turn(
        self,
        public_id: str,
        user_id: str,
        *,
        turn: Turn,
        user_item: UserMessageItem,
        title: str = "",
    ) -> None:
        """Record canonical turn start persistence."""
        self.calls.append((
            "start-turn",
            public_id,
            user_id,
            title,
            user_item.to_text(),
            dict(user_item.metadata),
            turn.model,
            turn.provider,
        ))

    def upsert_session_item(
        self,
        public_id: str,
        user_id: str,
        *,
        turn_id: str,
        item: SessionItem,
    ) -> None:
        """Record canonical session-item persistence."""
        self.calls.append((
            "upsert",
            public_id,
            user_id,
            item.type,
            item,
            turn_id,
        ))

    def complete_turn(
        self,
        public_id: str,
        user_id: str,
        *,
        turn_id: str,
        status: TurnStatus,
        error,
        completed_at,
        duration_ms: int | None,
        model: str | None,
        provider: str | None,
        usage: dict[str, Any] | None,
    ) -> None:
        """Record final turn persistence."""
        self.calls.append((
            "complete",
            public_id,
            user_id,
            turn_id,
            status,
            error,
            duration_ms,
            model,
            usage,
            provider,
        ))

    def append_turn_event(
        self,
        public_id: str,
        user_id: str,
        *,
        turn_id: str,
        event,
    ) -> None:
        """Record append-only turn event persistence."""
        self.calls.append((
            "append-event",
            public_id,
            user_id,
            turn_id,
            event.kind.value,
            event.seq,
            event.event_id,
            event.run_id,
        ))

    def load_messages(self, public_id: str, user_id: str) -> list[dict[str, Any]]:
        """Return no durable history for tests."""
        self.calls.append(("load", public_id, user_id))
        return []


class FakeFileService:
    """File service fake for chat turn tests."""

    def __init__(self) -> None:
        """Create a fake with one default non-image attachment."""
        self.assets = {
            "f1": FileAsset(
                file_uuid="f1",
                original_filename="notes.txt",
                uploader_public_id="user-1",
                uploaded_at=None,
                deleted_at=None,
                storage_bucket="icore-files",
                object_key="files/user-1/f1",
                storage_etag="etag",
                content_type="text/plain",
                checksum_sha256="a" * 64,
            )
        }

    def get_owned_asset(self, *, uploader_public_id: str, file_uuid: str) -> FileAsset:
        """Return a configured owned asset."""
        return self.assets[file_uuid]

    def create_download_url(self, *, uploader_public_id: str, file_uuid: str) -> str:
        """Return a deterministic image download URL."""
        return f"https://files.example/{file_uuid}"


class TrackingUserMemoryService:
    """Track compression checks and scheduled extraction calls."""

    def __init__(self) -> None:
        """Create a fake user memory service."""
        self.compression_checks: list[bool] = []
        self.extract_calls: list[dict[str, Any]] = []
        self.session_end_calls: list[dict[str, Any]] = []
        self.build_calls: list[tuple[str, Any]] = []

    def build_memory_prompt(self, user_id: str, turn: Any) -> str | None:
        """Return no injected memory prompt during chat turn tests."""
        return None

    def should_extract_on_compression(self, *, session_compressed: bool) -> bool:
        """Mirror production compression-only extraction rules."""
        self.compression_checks.append(session_compressed)
        return session_compressed

    async def extract_from_session(
        self,
        *,
        user_id: str,
        session_id: str,
        session_summary: str | None,
        recent_messages: list[dict[str, str]],
    ) -> None:
        """Record one compression-triggered extraction call."""
        self.extract_calls.append({
            "user_id": user_id,
            "session_id": session_id,
            "session_summary": session_summary,
            "recent_messages": recent_messages,
        })

    async def extract_on_session_end(
        self,
        *,
        user_id: str,
        session_id: str,
        session_summary: str | None,
        recent_messages: list[dict[str, str]],
    ) -> None:
        """Record one session-end extraction call."""
        self.session_end_calls.append({
            "user_id": user_id,
            "session_id": session_id,
            "session_summary": session_summary,
            "recent_messages": recent_messages,
        })


@dataclass
class FakeModelClient:
    """Model client fake with optional tool-call and delta behavior."""

    reply: str
    streaming: bool
    emit_tool_call: bool = False
    prompt_envelopes: list[PromptEnvelope] | None = None
    _sample_count: int = 0

    async def sample(self, prompt_envelope: PromptEnvelope) -> ModelStepResult:
        """Return a scripted model step for agent turn tests."""
        if self.prompt_envelopes is None:
            self.prompt_envelopes = []
        self.prompt_envelopes.append(prompt_envelope)
        self._sample_count += 1
        if self.emit_tool_call and self._sample_count == 1:
            return ModelStepResult(
                assistant_item=AgentMessageItem(text=""),
                tool_calls=[
                    ToolCallItem(
                        provider_tool_call_id="tool-1",
                        function=ToolFunction(
                            name="number_comparator",
                            arguments_text='{"left":2,"right":1}',
                            arguments_json={"left": 2, "right": 1},
                        ),
                    ),
                ],
                usage={"prompt_tokens": 1,
                       "completion_tokens": 1, "total_tokens": 2},
                model="test-model",
            )
        text = "Hi" if self.streaming else self.reply
        return ModelStepResult(
            assistant_item=AgentMessageItem(text=text),
            deltas=["Hi"] if self.streaming else [],
            usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            model="test-model",
        )


class FakeModelClientFactory:
    """Model-client factory fake that records construction kwargs."""

    def __init__(
        self,
        *,
        reply: str,
        streaming: bool = False,
        emit_tool_call: bool = False,
    ) -> None:
        """Create the factory fake."""
        self.calls: list[dict[str, Any]] = []
        self.client = FakeModelClient(
            reply=reply,
            streaming=streaming,
            emit_tool_call=emit_tool_call,
            prompt_envelopes=[],
        )

    def __call__(self, **kwargs) -> FakeModelClient:
        """Record factory kwargs and return the fake model client."""
        self.calls.append(kwargs)
        return self.client
