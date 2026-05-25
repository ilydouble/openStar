"""Tests for chat turn application services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from icore_agent.application.chat import (
    ChatStreamEventKind,
    ChatTurnCommand,
    ChatTurnService,
)
from icore_agent.application.chat.context import dedupe_file_uuids
from icore_agent.application.chat.routing import AgentHint, ChatIntent, resolve_routing
from icore_agent.domain.user import AuthenticatedUser


def test_resolve_routing_honors_agent_hint() -> None:
    """Explicit agent hints should select tool-enabled routing."""
    decision = resolve_routing("hello", "research")

    assert decision.intent is ChatIntent.TASK
    assert decision.enable_tools is True
    assert decision.agent_hint is AgentHint.RESEARCH


def test_dedupe_file_uuids_preserves_first_seen_order() -> None:
    """File UUID metadata should be deduplicated before message persistence."""
    assert dedupe_file_uuids((" a ", "b", "a", "", "b")) == ("a", "b")


@pytest.mark.asyncio
async def test_chat_turn_run_persists_messages_and_invokes_orchestrator() -> None:
    """Non-streaming chat turns should persist both sides and call the agent."""
    history = FakeHistory()
    memory = FakeMemory()
    factory = FakeOrchestratorFactory(reply="assistant reply")
    service = ChatTurnService(
        chat_history=history,
        file_service=FakeFileService(),
        conversation_memory=memory,
        orchestrator_factory=factory,
    )

    result = await service.run(_command(stream=False, file_uuids=("f1", "f1")))

    assert result.reply == "assistant reply"
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
    assert factory.calls[0]["enable_tools"] is False
    assert factory.agent.messages == []


@pytest.mark.asyncio
async def test_chat_turn_stream_emits_status_tokens_and_done() -> None:
    """Streaming chat turns should expose typed application events."""
    history = FakeHistory()
    memory = FakeMemory()
    factory = FakeOrchestratorFactory(reply="", streaming=True)
    service = ChatTurnService(
        chat_history=history,
        file_service=FakeFileService(),
        conversation_memory=memory,
        orchestrator_factory=factory,
    )

    event_stream = await service.stream(_command(stream=True, agent_hint="research"))
    events = []
    async for event in event_stream:
        events.append(event)
        if event.kind is ChatStreamEventKind.DONE:
            break

    assert [event.kind for event in events] == [
        ChatStreamEventKind.STATUS,
        ChatStreamEventKind.STATUS,
        ChatStreamEventKind.TOKEN,
        ChatStreamEventKind.TOKEN,
        ChatStreamEventKind.DONE,
    ]
    assert events[0].tool == "research_agent"
    assert events[1].tool == "web_search"
    assert "".join(
        event.text for event in events if event.kind is ChatStreamEventKind.TOKEN) == "Hi"
    assert history.calls[-1] == ("assistant", "session-1", "user-1", "Hi")


def _command(
    *,
    stream: bool,
    agent_hint: str = "",
    file_uuids: tuple[str, ...] = (),
) -> ChatTurnCommand:
    """Build one chat command for tests."""
    return ChatTurnCommand(
        message="Hello",
        session_id="session-1",
        stream=stream,
        tenant_code="",
        agent_hint=AgentHint(agent_hint) if agent_hint else None,
        file_uuids=file_uuids,
        display_caption=None,
        agent_message=None,
        template_id=None,
        user=_auth_user(),
    )


def _auth_user() -> AuthenticatedUser:
    """Build the authenticated domain user used by chat command tests."""
    return AuthenticatedUser(
        public_id="user-1",
        email="user@example.com",
        name="User One",
        roles=("owner",),
    )


class FakeMemory:
    """In-memory conversation cache fake."""

    def __init__(self) -> None:
        """Create the fake memory store."""
        self.appended: list[tuple[str, str, str]] = []

    async def get_context(self, session_id: str) -> tuple[str | None, list[dict]]:
        """Return an empty cached conversation."""
        return None, []

    async def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        """Record one appended cached message."""
        self.appended.append((session_id, role, content))


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
    ) -> None:
        """Record assistant message persistence."""
        self.calls.append(("assistant", public_id, user_id, content))

    def load_messages(self, public_id: str, user_id: str) -> list[dict[str, Any]]:
        """Return no durable history for tests."""
        self.calls.append(("load", public_id, user_id))
        return []


class FakeFileService:
    """Unused file service fake for chat turn tests."""


@dataclass
class FakeAgent:
    """Agent fake with optional stream callback behavior."""

    reply: str
    streaming: bool
    callback_handler: Any = None
    messages: list[dict[str, Any]] | None = None

    def __call__(self, message: str) -> str:
        """Return a reply or emit callback stream events."""
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

    def __init__(self, *, reply: str, streaming: bool = False) -> None:
        """Create the factory fake."""
        self.calls: list[dict[str, Any]] = []
        self.agent = FakeAgent(reply=reply, streaming=streaming, messages=[])

    def __call__(self, **kwargs) -> FakeAgent:
        """Record factory kwargs and return the fake agent."""
        self.calls.append(kwargs)
        self.agent.callback_handler = kwargs.get("callback_handler")
        return self.agent
