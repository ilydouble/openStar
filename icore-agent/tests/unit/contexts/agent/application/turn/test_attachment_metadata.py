"""Tests for attachment metadata owned by the agent turn application flow."""

from __future__ import annotations

from typing import Any

import pytest

from icore_agent.contexts.account.domain.user import AuthenticatedUser
from icore_agent.contexts.agent.application import AgentTurnService
from icore_agent.contexts.agent.domain.loop import ModelStepResult
from icore_agent.contexts.agent.domain.session import AgentMessageItem, UserMessageItem
from icore_agent.contexts.agent.domain.turn import AgentTurnCommand


@pytest.mark.asyncio
async def test_chat_turn_persists_display_caption_with_file_uuids() -> None:
    """User captions should be stored alongside attachment UUID metadata."""
    history = RecordingHistory()
    service = AgentTurnService(
        agent_session=history,
        file_service=EmptyFileService(),
        conversation_memory=NoopMemory(),
        model_client_factory=StaticModelClientFactory("ok"),
        usage_service=NoopUsageService(),
    )
    command = AgentTurnCommand(
        message="Please answer based on the data file I uploaded.",
        session_id="session-1",
        stream=False,
        tenant_code="",
        file_uuids=("file-1",),
        display_caption="Hello please analysis these files",
        agent_message="Creative Brief\n\n---\nPlease answer in markdown",
        template_id="image",
        incognito=False,
        user=AuthenticatedUser(
            public_id="user-1",
            email="user@example.com",
            name="User One",
            roles=("owner",),
        ),
    )

    await service.run(command)

    assert history.user_item_metadata == {
        "file_uuids": ["file-1"],
        "display_caption": "Hello please analysis these files",
        "template_id": "image",
    }


class RecordingHistory:
    """History fake that captures the turn's canonical user item metadata."""

    def __init__(self) -> None:
        """Create an empty metadata capture."""
        self.user_item_metadata: dict[str, Any] | None = None

    def ensure_owned_session(
        self,
        public_id: str,
        user_id: str,
        *,
        title: str = "",
    ) -> None:
        """Accept ownership checks for the test session."""

    def start_turn(
        self,
        public_id: str,
        user_id: str,
        *,
        turn: Any,
        user_item: UserMessageItem,
        title: str = "",
    ) -> None:
        """Capture metadata from the canonical user item."""
        self.user_item_metadata = dict(user_item.metadata)

    def upsert_session_item(self, *args: Any, **kwargs: Any) -> None:
        """Accept session item persistence."""

    def complete_turn(self, *args: Any, **kwargs: Any) -> None:
        """Accept terminal turn persistence."""

    def load_messages(self, public_id: str, user_id: str) -> list[dict[str, Any]]:
        """Return no persisted history for this isolated turn."""
        return []


class NoopMemory:
    """Conversation memory fake without persisted context."""

    async def get_context(
        self,
        session_id: str,
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Return an empty conversation snapshot."""
        return None, []

    async def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> bool:
        """Report that no compression occurred."""
        return False


class StaticModelClientFactory:
    """Model-client factory returning one static assistant response."""

    def __init__(self, reply: str) -> None:
        """Store the response returned by each constructed client."""
        self._reply = reply

    def __call__(self, **kwargs: Any) -> Any:
        """Return a model client with a fixed response."""
        reply = self._reply

        class ModelClient:
            """Small model client used for attachment metadata tests."""

            async def sample(self, prompt_envelope: Any) -> ModelStepResult:
                """Return the configured assistant response."""
                return ModelStepResult(
                    assistant_item=AgentMessageItem(text=reply),
                )

        return ModelClient()


class NoopUsageService:
    """Usage service fake that accepts quota and recording calls."""

    def check_quota(
        self,
        user_id: str,
        resource: str,
        amount: int = 1,
    ) -> tuple[bool, str | None]:
        """Allow quota checks."""
        return True, None

    def consume_quota(
        self,
        user_id: str,
        resource: str,
        amount: int = 1,
    ) -> None:
        """Accept quota consumption."""

    def consume_task(self, user_id: str) -> None:
        """Accept task consumption."""

    def record_llm_usage(self, **payload: Any) -> None:
        """Accept model usage recording."""


class EmptyFileService:
    """File service fake unused by this metadata-only turn."""
