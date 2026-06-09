"""Tests for agent turn application services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from icore_agent.application.agent import (
    AgentTurnCommand,
    AgentTurnService,
    AgentIntent,
    classify_turn_intent,
)
from icore_agent.application.agent.context import dedupe_file_uuids
from icore_agent.application.agent.tool import StrandsToolEventBridge
from icore_agent.domain.agent.turn import Turn, TurnEventKind, TurnStatus
from icore_agent.domain.user import AuthenticatedUser


def test_classify_turn_intent_classifies_task_keywords() -> None:
    """Intent classification should tag task-like messages for turn metadata."""
    intent = classify_turn_intent("帮我搜索今天的 AI 新闻")

    assert intent is AgentIntent.TASK


def test_dedupe_file_uuids_preserves_first_seen_order() -> None:
    """File UUID metadata should be deduplicated before message persistence."""
    assert dedupe_file_uuids((" a ", "b", "a", "", "b")) == ("a", "b")


@pytest.mark.asyncio
async def test_agent_turn_run_persists_messages_and_invokes_orchestrator() -> None:
    """Non-streaming agent turns should persist both sides and call the agent."""
    history = FakeHistory()
    memory = FakeMemory()
    factory = FakeOrchestratorFactory(reply="assistant reply")
    usage = FakeUsageService()
    service = AgentTurnService(
        agent_session=history,
        file_service=FakeFileService(),
        conversation_memory=memory,
        orchestrator_factory=factory,
        usage_service=usage,
    )

    turn = await service.run(_command(stream=False, file_uuids=("f1", "f1")))

    assert isinstance(turn, Turn)
    assert turn.session_id == "session-1"
    assert turn.status is TurnStatus.COMPLETED
    assert turn.reply_text() == "assistant reply"
    assert history.calls == [
        ("ensure", "session-1", "user-1", "Hello"),
        ("user", "session-1", "user-1", "Hello", {"file_uuids": ["f1"]}),
        ("load", "session-1", "user-1"),
        ("assistant", "session-1", "user-1", "assistant reply"),
    ]
    assert memory.appended == [
        ("session-1", "user", "Hello"),
        ("session-1", "assistant", "assistant reply"),
    ]
    assert "enable_tools" not in factory.calls[0]
    assert "agent_hint" not in factory.calls[0]
    assert len(factory.calls[0]["hooks"]) == 1
    assert isinstance(factory.calls[0]["hooks"][0], StrandsToolEventBridge)
    assert factory.agent.messages == []
    assert usage.calls == [("user-1", "tasks", 1)]
    assert len(usage.llm_calls) == 1
    assert usage.llm_calls[0]["user_id"] == "user-1"
    assert usage.llm_calls[0]["total_tokens"] > 0


@pytest.mark.asyncio
async def test_agent_turn_run_links_recorded_tool_calls_to_assistant() -> None:
    """Completed agent turns should attach observed tool calls to the assistant row."""
    history = FakeHistory()
    service = AgentTurnService(
        agent_session=history,
        file_service=FakeFileService(),
        conversation_memory=FakeMemory(),
        orchestrator_factory=FakeOrchestratorFactory(
            reply="assistant reply",
            emit_tool_call=True,
        ),
        usage_service=FakeUsageService(),
    )

    turn = await service.run(_command(stream=False))

    assert turn.reply_text() == "assistant reply"
    assert (
        "tool-link",
        "session-1",
        ("tool-1",),
        99,
    ) in history.calls


@pytest.mark.asyncio
async def test_agent_turn_run_skips_user_memory_without_compression() -> None:
    """Normal turns should not trigger durable memory extraction."""
    memory_service = TrackingUserMemoryService()
    service = AgentTurnService(
        agent_session=FakeHistory(),
        file_service=FakeFileService(),
        conversation_memory=FakeMemory(),
        orchestrator_factory=FakeOrchestratorFactory(reply="assistant reply"),
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
        orchestrator_factory=FakeOrchestratorFactory(reply="assistant reply"),
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
        orchestrator_factory=FakeOrchestratorFactory(reply="", streaming=True),
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
    factory = FakeOrchestratorFactory(reply="", streaming=True)
    service = AgentTurnService(
        agent_session=history,
        file_service=FakeFileService(),
        conversation_memory=memory,
        orchestrator_factory=factory,
        usage_service=FakeUsageService(),
    )

    event_stream = await service.stream(_command(stream=True))
    events = []
    async for event in event_stream:
        events.append(event)
        if event.kind is TurnEventKind.TURN_COMPLETED:
            break

    assert [event.kind for event in events] == [
        TurnEventKind.TURN_STARTED,
        TurnEventKind.ITEM_COMPLETED,
        TurnEventKind.ITEM_STARTED,
        TurnEventKind.ITEM_STARTED,
        TurnEventKind.ITEM_DELTA,
        TurnEventKind.ITEM_COMPLETED,
        TurnEventKind.TURN_COMPLETED,
    ]
    assert events[3].item.function.name == "web_search"
    assert "".join(
        event.delta["text"]
        for event in events
        if event.kind is TurnEventKind.ITEM_DELTA
    ) == "Hi"
    assert ("assistant", "session-1", "user-1", "Hi") in history.calls


@pytest.mark.asyncio
async def test_agent_turn_run_incognito_skips_history_and_memory_extract() -> None:
    """Incognito turns should skip PostgreSQL persistence and memory extraction."""
    history = FakeHistory()
    memory_service = TrackingUserMemoryService()
    conversation_memory = FakeMemory(compress_on_append=True)
    factory = FakeOrchestratorFactory(reply="assistant reply")
    service = AgentTurnService(
        agent_session=history,
        file_service=FakeFileService(),
        conversation_memory=conversation_memory,
        orchestrator_factory=factory,
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
    assert len(factory.calls[0]["hooks"]) == 1
    assert isinstance(factory.calls[0]["hooks"][0], StrandsToolEventBridge)
    assert factory.calls[0]["user_memory_prompt"] is None


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
    factory = FakeOrchestratorFactory(reply="assistant reply")
    service = AgentTurnService(
        agent_session=FakeHistory(),
        file_service=FakeFileService(),
        conversation_memory=FakeMemory(),
        orchestrator_factory=factory,
        usage_service=FakeUsageService(),
        user_memory_service=memory_service,
    )

    await service.run(_command(stream=False, incognito=True))

    assert memory_service.build_calls == []
    assert factory.calls[0]["user_memory_prompt"] is None


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

    def save_user_message(
        self,
        public_id: str,
        user_id: str,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record user message persistence."""
        self.calls.append(("user", public_id, user_id, content, metadata))

    def save_assistant_message(
        self,
        public_id: str,
        user_id: str,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Record assistant message persistence."""
        self.calls.append(("assistant", public_id, user_id, content))
        return 99

    def save_tool_message(
        self,
        public_id: str,
        user_id: str,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Record tool message persistence."""
        self.calls.append(("tool-message", public_id,
                          user_id, content, metadata))
        return 42

    def start_tool_call(
        self,
        public_id: str,
        *,
        tool_call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> None:
        """Record tool call start persistence."""
        self.calls.append((
            "tool-start",
            public_id,
            tool_call_id,
            tool_name,
            arguments,
        ))

    def finish_tool_call(
        self,
        public_id: str,
        *,
        tool_call_id: str,
        status: str,
        result: dict[str, Any] | None,
        error_code: str | None,
        error_message: str | None,
        elapsed_ms: int | None,
        tool_message_id: int | None,
    ) -> None:
        """Record tool call finish persistence."""
        self.calls.append((
            "tool-finish",
            public_id,
            tool_call_id,
            status,
            result,
            error_code,
            error_message,
            tool_message_id,
        ))

    def attach_tool_calls_to_assistant(
        self,
        public_id: str,
        *,
        tool_call_ids: tuple[str, ...],
        assistant_message_id: int,
    ) -> None:
        """Record assistant-message linking."""
        self.calls.append((
            "tool-link",
            public_id,
            tool_call_ids,
            assistant_message_id,
        ))

    def load_messages(self, public_id: str, user_id: str) -> list[dict[str, Any]]:
        """Return no durable history for tests."""
        self.calls.append(("load", public_id, user_id))
        return []


class FakeFileService:
    """Unused file service fake for chat turn tests."""


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
class FakeAgent:
    """Agent fake with optional stream callback behavior."""

    reply: str
    streaming: bool
    emit_tool_call: bool = False
    callback_handler: Any = None
    hooks: list[Any] | None = None
    messages: list[dict[str, Any]] | None = None

    def __call__(self, message: str) -> str:
        """Return a reply or emit callback stream events."""
        if self.emit_tool_call:
            tool_use = {
                "toolUseId": "tool-1",
                "name": "web_search",
                "input": {"q": message},
            }
            for hook in self.hooks or []:
                hook.record_start(tool_use)
                hook.record_finish(
                    tool_use,
                    {
                        "toolUseId": "tool-1",
                        "status": "success",
                        "content": [{"text": "ok"}],
                    },
                    exception=None,
                )
        if self.streaming and self.callback_handler is not None:
            self.callback_handler(
                current_tool_use={
                    "toolUseId": "tool-1",
                    "name": "web_search",
                    "input": {"q": message},
                }
            )
            self.callback_handler(data="Hi")
        return self.reply


class FakeOrchestratorFactory:
    """Orchestrator factory fake that records construction kwargs."""

    def __init__(
        self,
        *,
        reply: str,
        streaming: bool = False,
        emit_tool_call: bool = False,
    ) -> None:
        """Create the factory fake."""
        self.calls: list[dict[str, Any]] = []
        self.agent = FakeAgent(
            reply=reply,
            streaming=streaming,
            emit_tool_call=emit_tool_call,
            messages=[],
        )

    def __call__(self, **kwargs) -> FakeAgent:
        """Record factory kwargs and return the fake agent."""
        self.calls.append(kwargs)
        self.agent.callback_handler = kwargs.get("callback_handler")
        self.agent.hooks = kwargs.get("hooks")
        return self.agent
