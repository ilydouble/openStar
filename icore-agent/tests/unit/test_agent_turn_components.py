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
from icore_agent.domain.agent.turn import AgentTurnCommand
from icore_agent.domain.agent.loop import ModelStepResult
from icore_agent.domain.agent.prompt import PromptEnvelope
from icore_agent.domain.agent.session import (
    AgentMessageItem,
    ContextItem,
    SessionItemStatus,
    ToolCallItem,
    ToolCallResult,
    ToolCallStatus,
    ToolFunction,
    UserInput,
    UserInputType,
    UserMessageItem,
)
from icore_agent.domain.agent.turn import Turn, TurnError, TurnEvent, TurnStatus
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


def test_turn_lifecycle_marks_aborted_turn_as_interrupted() -> None:
    """TurnLifecycle should expose aborted turns as interrupted lifecycle state."""
    started_at = datetime(2026, 6, 8, 1, 2, 3, tzinfo=UTC)
    completed_at = started_at + timedelta(milliseconds=500)
    lifecycle = TurnLifecycle.start(
        session_id="session-1",
        started_at=started_at,
    )
    lifecycle.apply_agent_event(TurnEvent.item_completed(
        session_id="session-1",
        turn_id=lifecycle.turn.id,
        item=AgentMessageItem(text="partial"),
    ))

    final = lifecycle.aborted(completed_at=completed_at)

    assert final.status is TurnStatus.INTERRUPTED
    assert final.event.kind == "turn_aborted"
    assert final.event.reply == "partial"
    assert final.duration_ms == 500


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
        model="test-model",
        provider="test-provider",
        usage={"total_tokens": 1},
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
        model="test-model",
        provider="test-provider",
        usage={"total_tokens": 2},
    )

    assert history.calls == ["create", "upsert", "complete"]


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

    compressed = await recorder.append_memory_pair(command, "assistant reply")
    await recorder.maybe_extract_user_memory(command, compressed)

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


def test_turn_usage_recorder_handles_quota_and_model_usage(monkeypatch) -> None:
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
    assert recorder.turn_usage() == {
        "model": "test-model",
        "provider": None,
        "usage": {
            "prompt_tokens": 3,
            "completion_tokens": 3,
            "total_tokens": 6,
        },
    }


def test_agent_turn_runner_factory_builds_runner_and_loop_request() -> None:
    """AgentTurnRunnerFactory should hide concrete model/tool construction details."""
    factory = RecordingModelClientFactory()
    runner_factory = AgentTurnRunnerFactory(
        factory,
    )
    command = _command(stream=False)
    context = StubContext()
    request = runner_factory.build_loop_request(
        command=command,
        context=context,
        turn=Turn(session_id="session-1", id="turn-1"),
    )
    prompt_envelope = request.context_manager.build_prompt(
        turn=request.turn,
        session_items=[],
        tools=request.tool_runtime.visible_tools(),
    )

    assert request.session_id == "session-1"
    assert request.turn_id == "turn-1"
    assert prompt_envelope.current_user_item.content[0].text == "Hello"
    attachment_context = "\n".join(
        item.content
        for item in prompt_envelope.context_items
        if item.kind == "file_attachment"
    )
    assert 'file_attachment filename="notes.txt" uuid="file-1"' in attachment_context
    assert "read_uploaded_file" in attachment_context
    assert request.model_client is factory.client
    assert prompt_envelope.history_items[0].content[0].text == "old"
    assert prompt_envelope.tools
    assert "enable_tools" not in factory.calls[0]
    assert "agent_hint" not in factory.calls[0]
    assert "attachments_text" not in factory.calls[0]
    assert "data_attachments" not in factory.calls[0]
    assert "file_service" not in factory.calls[0]
    assert "prompt_envelope" not in factory.calls[0]
    assert "tool_definitions" not in factory.calls[0]
    assert "hooks" not in factory.calls[0]


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
    """History fake for transcript tests."""

    def __init__(self) -> None:
        """Create the fake."""
        self.calls: list[tuple] = []


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
    image_attachments = [object()]
    file_attachments = [object(), object()]
    user_memory_prompt = "remember"
    history_items = [
        UserMessageItem(content=[
            UserInput(type=UserInputType.TEXT, text="old"),
        ]),
    ]
    has_attachments = True

    def to_context_items(
        self,
        *,
        include_image_refs: bool = True,
    ) -> list[ContextItem]:
        """Return context items in the domain AgentContext shape."""
        _ = include_image_refs
        return [
            ContextItem(kind="session_summary", content="summary"),
            ContextItem(kind="user_memory", content="remember"),
            ContextItem(
                kind="file_attachment",
                content=(
                    'file_attachment filename="notes.txt" uuid="file-1"\n'
                    "Use read_uploaded_file with the uuid when "
                    "file_attachment contents are needed."
                ),
            ),
        ]

    def to_current_user_inputs(
        self,
        user_text: str,
        *,
        include_image_inputs: bool,
    ) -> list[UserInput]:
        """Return current user input blocks in the domain AgentContext shape."""
        _ = include_image_inputs
        return [UserInput(type=UserInputType.TEXT, text=user_text)]


class StubSettings:
    """Settings fake with a stable model id."""

    def effective_model_id(self) -> str:
        """Return the model id used for estimated usage."""
        return "test-model"


class RecordingModelClient:
    """Model client fake."""

    prompt_envelopes: list[PromptEnvelope]

    def __init__(self) -> None:
        """Create the fake."""
        self.prompt_envelopes = []

    async def sample(self, prompt_envelope: PromptEnvelope) -> ModelStepResult:
        """Record a prompt and return a fixed model step."""
        self.prompt_envelopes.append(prompt_envelope)
        return ModelStepResult(
            assistant_item=AgentMessageItem(
                text=(
                    "reply to "
                    f"{prompt_envelope.current_user_item.content[0].text}"
                ),
            ),
        )


class RecordingModelClientFactory:
    """Model-client factory fake."""

    def __init__(self) -> None:
        """Create the fake."""
        self.calls: list[dict[str, Any]] = []
        self.client = RecordingModelClient()

    def __call__(self, **kwargs: Any) -> RecordingModelClient:
        """Record construction kwargs."""
        self.calls.append(kwargs)
        return self.client


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
