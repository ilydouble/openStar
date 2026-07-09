from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from icore_agent.contexts.memory.application.session_context import resolve_session_extract_context


class FakeConversationMemory:
    """Minimal conversation memory fake for session context tests."""

    def __init__(
        self,
        *,
        summary: str = "",
        messages: list[dict[str, str]] | None = None,
    ) -> None:
        """Create one fake redis-backed conversation snapshot."""
        self.summary = summary
        self.messages = messages or []

    async def get_context(self, session_id: str) -> tuple[str, list[dict[str, str]]]:
        """Return the configured redis snapshot."""
        return self.summary, self.messages


class FakeAgentSession:
    """Minimal agent session fake for session context tests."""

    def __init__(self, messages: list[dict[str, str]] | None = None) -> None:
        """Create one fake persisted message list."""
        self.messages = messages or []

    def load_messages(self, public_id: str, user_id: str) -> list[dict[str, str]]:
        """Return the configured persisted messages."""
        return self.messages


@pytest.mark.asyncio
async def test_resolve_session_extract_context_prefers_redis_snapshot() -> None:
    """Redis summary and messages should win over persisted history."""
    summary, messages = await resolve_session_extract_context(
        "session-1",
        user_id="u1",
        conversation_memory=FakeConversationMemory(
            summary="Older turns summarized",
            messages=[{"role": "user", "content": "Latest question"}],
        ),
        agent_session=FakeAgentSession([
            {"role": "user", "content": "Persisted only"},
        ]),
    )

    assert summary == "Older turns summarized"
    assert messages == [{"role": "user", "content": "Latest question"}]


@pytest.mark.asyncio
async def test_resolve_session_extract_context_falls_back_to_persisted_messages() -> None:
    """Persisted messages should be used when redis cache is empty."""
    summary, messages = await resolve_session_extract_context(
        "session-1",
        user_id="u1",
        conversation_memory=FakeConversationMemory(),
        agent_session=FakeAgentSession([
            {"role": "user", "content": "Persisted question", "metadata": {}},
            {"role": "assistant", "content": "Persisted answer"},
        ]),
    )

    assert summary == ""
    assert messages == [
        {"role": "user", "content": "Persisted question"},
        {"role": "assistant", "content": "Persisted answer"},
    ]
