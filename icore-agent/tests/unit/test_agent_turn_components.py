"""Tests for agent turn application collaborators."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from icore_agent.application.agent.turn import (
    AgentTurnRunnerFactory,
    TurnLifecycle,
    TurnPersistence,
    TurnTranscriptRecorder,
    TurnUsageRecorder,
)
from icore_agent.application.agent.tool import TurnToolProjection
from icore_agent.application.agent import AgentTurnCommand
from icore_agent.domain.agent.session import (
    AgentMessageItem,
    SessionItemStatus,
    ToolCallItem,
    ToolCallResult,
    ToolCallStatus,
    ToolFunction,
)
from icore_agent.domain.agent.turn import TurnError, TurnEvent, TurnStatus
from icore_agent.domain.user import AuthenticatedUser


def test_turn_lifecycle_tracks_user_item_reply_and_completion() -> None:
    """TurnLifecycle should own turn id, user item, reply, and final metadata."""
    started_at = datetime(2026, 6, 8, 1, 2, 3, tzinfo=UTC)
    completed_at = started_at + timedelta(milliseconds=1250)
    lifecycle = TurnLifecycle.start(
        session_id="session-1",
        started_at=started_at,
    )

    started = lifecycle.started_event()
    user_event = lifecycle.user_message_event("Hello")
    lifecycle.apply_agent_event(TurnEvent.item_delta(
        session_id="session-1",
        turn_id=lifecycle.turn.id,
        item_id="assistant-1",
        delta={"text": "Hel"},
    ))
    lifecycle.apply_agent_event(TurnEvent.item_completed(
        session_id="session-1",
        turn_id=lifecycle.turn.id,
        item=AgentMessageItem(
            id="assistant-1",
            status=SessionItemStatus.COMPLETED,
            text="Hello back",
            created_at=started_at,
            completed_at=completed_at,
        ),
    ))
    final = lifecycle.completed(completed_at=completed_at)

    assert started.turn_id == lifecycle.turn.id
    assert user_event.item.content[0].text == "Hello"
    assert lifecycle.reply == "Hello back"
    assert lifecycle.turn.items[0].id == user_event.item.id
    assert lifecycle.turn.items[1].id == "assistant-1"
    assert final.status is TurnStatus.COMPLETED
    assert final.duration_ms == 1250
    assert final.event.reply == "Hello back"
    assert final.event.turn is lifecycle.turn
    assert final.event.turn.reply_text() == "Hello back"


def test_turn_persistence_skips_incognito_and_swallows_storage_errors() -> None:
    """TurnPersistence should keep persistence failures out of turn execution."""
    history = FailingHistory()
    persistence = TurnPersistence(history)
    lifecycle = TurnLifecycle.start(session_id="session-1")
    command = _command(stream=False, incognito=True)

    persistence.create(command, lifecycle.turn)
    persistence.persist_event(command, lifecycle.user_message_event("Hello"))
    persistence.complete(
        command,
        turn_id=lifecycle.turn.id,
        status=TurnStatus.COMPLETED,
        error=None,
        completed_at=datetime.now(UTC),
        duration_ms=1,
    )

    assert history.calls == []

    command = _command(stream=False, incognito=False)
    persistence.create(command, lifecycle.turn)
    persistence.persist_event(command, lifecycle.user_message_event("Hello"))
    persistence.complete(
        command,
        turn_id=lifecycle.turn.id,
        status=TurnStatus.FAILED,
        error=TurnError(message="boom"),
        completed_at=datetime.now(UTC),
        duration_ms=2,
    )

    assert history.calls == ["create", "upsert", "complete"]


def test_turn_tool_projection_persists_tool_item_and_links_assistant() -> None:
    """TurnToolProjection should project SessionItem tool calls into legacy tables."""
    history = RecordingHistory()
    projection = TurnToolProjection(history)
    command = _command(stream=False)
    tool_item = ToolCallItem(
        id="item-tool-1",
        provider_tool_call_id="provider-tool-1",
        status=ToolCallStatus.COMPLETED,
        function=ToolFunction(
            name="web_search",
            arguments_json={"q": "weather"},
        ),
        result=ToolCallResult(structured_content={"ok": True}),
        duration_ms=42,
    )

    projection.persist_event(command, TurnEvent.item_started(
        session_id="session-1",
        turn_id="turn-1",
        item=tool_item,
    ))
    projection.persist_event(command, TurnEvent.item_completed(
        session_id="session-1",
        turn_id="turn-1",
        item=tool_item,
    ))
    projection.attach_to_assistant(command, assistant_message_id=99)

    assert projection.tool_call_ids == ("provider-tool-1",)
    assert history.calls == [
        (
            "tool-start",
            "session-1",
            "provider-tool-1",
            "web_search",
            {"q": "weather"},
        ),
        (
            "tool-message",
            "session-1",
            "user-1",
            '{"ok":true}',
            {
                "tool_call_id": "provider-tool-1",
                "tool_name": "web_search",
            },
        ),
        (
            "tool-finish",
            "session-1",
            "provider-tool-1",
            "success",
            {"ok": True},
            None,
            None,
            42,
            42,
        ),
        ("tool-link", "session-1", ("provider-tool-1",), 99),
    ]


@pytest.mark.asyncio
async def test_turn_transcript_recorder_appends_memory_and_extracts_on_compression() -> None:
    """TurnTranscriptRecorder should isolate conversation history side effects."""
    history = RecordingHistory()
    memory = CompressingMemory()
    user_memory = RecordingUserMemory()
    recorder = TurnTranscriptRecorder(
        agent_session=history,
        conversation_memory=memory,
        user_memory_service=user_memory,
    )
    command = _command(stream=False)

    assistant_id = recorder.save_assistant_message(command, "assistant reply")
    compressed = await recorder.append_memory_pair(command, "assistant reply")
    await recorder.maybe_extract_user_memory(command, compressed)

    assert assistant_id == 99
    assert memory.appended == [
        ("session-1", "user", "Hello"),
        ("session-1", "assistant", "assistant reply"),
    ]
    assert user_memory.extract_calls == [{
        "user_id": "user-1",
        "session_id": "session-1",
        "session_summary": "summary",
        "recent_messages": [{"role": "user", "content": "Hello"}],
    }]


def test_turn_usage_recorder_handles_quota_and_runner_usage(monkeypatch) -> None:
    """TurnUsageRecorder should keep quota and LLM usage capture out of the service."""
    usage = RecordingUsageService()
    recorder = TurnUsageRecorder(usage)
    command = _command(stream=False)
    context = StubContext()

    recorder.check_task_quota(command)
    recorder.record_attachment_quota(command, context)
    recorder.consume_task(command)
    monkeypatch.setattr(
        "icore_agent.application.agent.turn.usage.settings",
        StubSettings(),
    )
    monkeypatch.setattr(
        "icore_agent.application.agent.turn.usage.token_counter",
        lambda **kwargs: 3,
    )
    recorder.record_estimated_turn_usage(
        command,
        prompt="Hello",
        reply="assistant reply",
    )

    assert usage.calls == [
        ("check", "user-1", "tasks", 1),
        ("consume", "user-1", "attachments", 3),
        ("consume_task", "user-1"),
    ]
    assert usage.llm_calls == [{
        "user_id": "user-1",
        "session_id": "session-1",
        "model": "test-model",
        "prompt_tokens": 3,
        "completion_tokens": 3,
        "total_tokens": 6,
    }]


def test_agent_turn_runner_factory_builds_runner_and_loop_request() -> None:
    """AgentTurnRunnerFactory should hide concrete runner construction details."""
    factory = RecordingOrchestratorFactory()
    runner_factory = AgentTurnRunnerFactory(
        factory,
        tool_bridge_factory=FakeToolBridge,
    )
    command = _command(stream=False)
    context = StubContext()
    request = runner_factory.build_loop_request(
        command=command,
        context=context,
        turn_id="turn-1",
        invoke=lambda runner, message: runner(message),
    )

    assert request.session_id == "session-1"
    assert request.turn_id == "turn-1"
    assert request.message.startswith("Hello\n\nAttached files for this turn:")
    assert 'file_attachment filename="notes.txt" uuid="file-1"' in request.message
    assert "read_uploaded_file" in request.message
    assert request.runner is factory.runner
    assert request.history_messages == [{"role": "user", "content": "old"}]
    assert isinstance(request.tool_bridge, FakeToolBridge)
    assert "enable_tools" not in factory.calls[0]
    assert "agent_hint" not in factory.calls[0]
    assert "attachments_text" not in factory.calls[0]
    assert "data_attachments" not in factory.calls[0]
    assert factory.calls[0]["file_service"] is None
    assert len(factory.calls[0]["hooks"]) == 1


class FailingHistory:
    """History fake that records calls and raises for normal turns."""

    def __init__(self) -> None:
        """Create the fake."""
        self.calls: list[str] = []

    def create_turn(self, *args: Any, **kwargs: Any) -> None:
        """Record and fail turn creation."""
        self.calls.append("create")
        raise LookupError("missing session")

    def upsert_session_item(self, *args: Any, **kwargs: Any) -> None:
        """Record and fail item persistence."""
        self.calls.append("upsert")
        raise LookupError("missing turn")

    def complete_turn(self, *args: Any, **kwargs: Any) -> None:
        """Record and fail turn completion."""
        self.calls.append("complete")
        raise LookupError("missing turn")


class RecordingHistory:
    """History fake for transcript and tool projection tests."""

    def __init__(self) -> None:
        """Create the fake."""
        self.calls: list[tuple] = []

    def save_assistant_message(
        self,
        public_id: str,
        user_id: str,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Record assistant message persistence."""
        self.calls.append(("assistant", public_id, user_id, content, metadata))
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
        """Record tool-call start."""
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
        """Record tool-call finish."""
        self.calls.append((
            "tool-finish",
            public_id,
            tool_call_id,
            status,
            result,
            error_code,
            error_message,
            elapsed_ms,
            tool_message_id,
        ))

    def attach_tool_calls_to_assistant(
        self,
        public_id: str,
        *,
        tool_call_ids: tuple[str, ...],
        assistant_message_id: int,
    ) -> None:
        """Record tool-call to assistant linking."""
        self.calls.append((
            "tool-link",
            public_id,
            tool_call_ids,
            assistant_message_id,
        ))


class CompressingMemory:
    """Conversation memory fake that always reports compression."""

    def __init__(self) -> None:
        """Create the fake."""
        self.appended: list[tuple[str, str, str]] = []

    async def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> bool:
        """Record one append and report compression."""
        self.appended.append((session_id, role, content))
        return True

    async def get_context(self, session_id: str) -> tuple[str, list[dict[str, str]]]:
        """Return context used for durable memory extraction."""
        return "summary", [{"role": "user", "content": "Hello"}]


class RecordingUserMemory:
    """User memory fake for extraction scheduling."""

    def __init__(self) -> None:
        """Create the fake."""
        self.extract_calls: list[dict[str, Any]] = []

    def should_extract_on_compression(self, *, session_compressed: bool) -> bool:
        """Extract whenever compression happened."""
        return session_compressed

    async def extract_from_session(
        self,
        *,
        user_id: str,
        session_id: str,
        session_summary: str | None,
        recent_messages: list[dict[str, str]],
    ) -> None:
        """Record durable memory extraction."""
        self.extract_calls.append({
            "user_id": user_id,
            "session_id": session_id,
            "session_summary": session_summary,
            "recent_messages": recent_messages,
        })


class RecordingUsageService:
    """Usage service fake for TurnUsageRecorder tests."""

    def __init__(self) -> None:
        """Create the fake."""
        self.calls: list[tuple] = []
        self.llm_calls: list[dict[str, Any]] = []

    def check_quota(
        self,
        user_id: str,
        resource: str,
        amount: int = 1,
    ) -> tuple[bool, str | None]:
        """Record an allowed quota check."""
        self.calls.append(("check", user_id, resource, amount))
        return True, None

    def consume_quota(self, user_id: str, resource: str, amount: int = 1) -> None:
        """Record quota consumption."""
        self.calls.append(("consume", user_id, resource, amount))

    def consume_task(self, user_id: str) -> None:
        """Record task consumption."""
        self.calls.append(("consume_task", user_id))

    def record_llm_usage(self, **payload: Any) -> None:
        """Record LLM usage."""
        self.llm_calls.append(payload)


class StubContext:
    """Minimal agent context test double."""

    summary = "summary"
    image_attachment_payloads = [{"file_uuid": "image-1"}]
    file_attachment_payloads = [
        {"filename": "notes.txt", "file_uuid": "file-1"},
        {"filename": "data.csv", "file_uuid": "file-2"},
    ]
    image_attachments = [object()]
    file_attachments = [object(), object()]
    user_memory_prompt = "remember"
    runner_history = [{"role": "user", "content": "old"}]
    has_attachments = True


class FakeToolBridge:
    """Tool bridge fake for runner factory tests."""

    def __init__(self, *, session_id: str, turn_id: str) -> None:
        """Create the fake bridge."""
        self.session_id = session_id
        self.turn_id = turn_id

    def on_callback(self, **kwargs: Any) -> None:
        """Accept provider callbacks."""

    def bound_to(self, **kwargs: Any):
        """Return a no-op context manager."""

        class _Context:
            def __enter__(self) -> None:
                return None

            def __exit__(self, exc_type, exc, traceback) -> None:
                return None

        return _Context()


class StubSettings:
    """Settings fake with a stable model id."""

    def effective_model_id(self) -> str:
        """Return the model id used for estimated usage."""
        return "test-model"


class RecordingRunner:
    """Prepared agent fake."""

    messages: list[dict[str, Any]]

    def __call__(self, message: str) -> str:
        """Return a fixed reply."""
        return f"reply to {message}"


class RecordingOrchestratorFactory:
    """Orchestrator factory fake."""

    def __init__(self) -> None:
        """Create the fake."""
        self.calls: list[dict[str, Any]] = []
        self.runner = RecordingRunner()

    def __call__(self, **kwargs: Any) -> RecordingRunner:
        """Record construction kwargs."""
        self.calls.append(kwargs)
        return self.runner


def _command(
    *,
    stream: bool,
    incognito: bool = False,
) -> AgentTurnCommand:
    """Build one chat command for agent-turn collaborator tests."""
    return AgentTurnCommand(
        message="Hello",
        session_id="session-1",
        stream=stream,
        tenant_code="",
        file_uuids=(),
        display_caption=None,
        agent_message=None,
        template_id=None,
        incognito=incognito,
        user=AuthenticatedUser(
            public_id="user-1",
            email="user@example.com",
            name="User One",
            roles=("owner",),
        ),
    )
