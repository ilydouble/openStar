"""Tests for session state attachment metadata and asset mode mapping."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from icore_agent.contexts.agent.application import AgentSessionService, AgentTurnService
from icore_agent.contexts.agent.domain.loop import ModelStepResult
from icore_agent.contexts.agent.domain.session import (
    AgentMessageItem,
    UserInput,
    UserInputType,
    UserMessageItem,
)
from icore_agent.contexts.agent.domain.turn import AgentTurnCommand, Turn, TurnStatus
from icore_agent.contexts.files.domain.models import FileAsset
from icore_agent.contexts.account.domain.user import AuthenticatedUser
from icore_agent.contexts.agent.interfaces.http.v1.handlers.session import (
    _asset_mode,
    _session_attachment_refs,
)


def test_asset_mode_classifies_supported_document_types_as_data() -> None:
    """Document uploads should map to the frontend data attachment mode."""
    assert _asset_mode("report.pdf", "application/pdf") == "data"
    assert _asset_mode(
        "notes.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document") == "data"
    assert _asset_mode("readme.md", "text/markdown") == "data"
    assert _asset_mode("photo.png", "image/png") == "image"


def test_session_attachment_refs_include_pdf_as_data_mode() -> None:
    """PDF assets should resolve into session attachment refs for UI hydration."""
    file_uuid = str(uuid4())
    service = _FakeFileService({
        file_uuid: _asset(file_uuid, "report.pdf", "application/pdf"),
    })

    refs = _session_attachment_refs(
        [
            {
                "items": [
                    {
                        "type": "user_message",
                        "metadata": {"file_uuids": [file_uuid]},
                    },
                ],
            },
        ],
        user_id="user-public-id",
        file_service=service,
    )

    assert len(refs) == 1
    assert refs[0].mode == "data"
    assert refs[0].original_filename == "report.pdf"


@pytest.mark.asyncio
async def test_chat_turn_persists_display_caption_with_file_uuids() -> None:
    """User captions should be stored alongside attachment UUID metadata."""
    history = _RecordingHistory()
    service = AgentTurnService(
        agent_session=history,
        file_service=_FakeFileService({}),
        conversation_memory=_NoopMemory(),
        model_client_factory=_StaticModelClientFactory("ok"),
        usage_service=_NoopUsageService(),
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
        user=_auth_user(),
    )

    await service.run(command)

    assert history.user_item_metadata == {
        "file_uuids": ["file-1"],
        "display_caption": "Hello please analysis these files",
        "template_id": "image",
    }


def test_chat_history_projects_display_caption_metadata() -> None:
    """Display captions should round-trip through canonical user item persistence."""
    service = AgentSessionService()
    session_id = f"session-{uuid4()}"
    user_id = f"user-{uuid4()}"
    file_uuid = str(uuid4())

    service.ensure_owned_session(session_id, user_id, title="Analyze files")
    turn = Turn(session_id=session_id)
    service.start_turn(
        session_id,
        user_id,
        turn=turn,
        user_item=UserMessageItem(
            content=[
                UserInput(
                    type=UserInputType.TEXT,
                    text="Please answer based on the images and data files I uploaded.",
                ),
            ],
            metadata={
                "file_uuids": [file_uuid],
                "display_caption": "Hello please analysis these files",
            },
        ),
        title="Analyze files",
    )
    service.complete_turn(
        session_id,
        user_id,
        turn_id=turn.id,
        status=TurnStatus.COMPLETED,
        error=None,
        completed_at=datetime.now(UTC),
        duration_ms=1,
        model="test-model",
        provider="test-provider",
        usage={"total_tokens": 1},
    )

    messages = service.load_messages(session_id, user_id)
    assert messages[0]["metadata"] == {
        "file_uuids": [file_uuid],
        "display_caption": "Hello please analysis these files",
    }


def _auth_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        public_id="user-1",
        email="user@example.com",
        name="User One",
        roles=("owner",),
    )


class _RecordingHistory:
    def __init__(self) -> None:
        self.user_item_metadata: dict[str, Any] | None = None

    def ensure_owned_session(self, public_id: str, user_id: str, *, title: str = "") -> None:
        return None

    def start_turn(
        self,
        public_id: str,
        user_id: str,
        *,
        turn,
        user_item: UserMessageItem,
        title: str = "",
    ) -> None:
        self.user_item_metadata = dict(user_item.metadata)

    def upsert_session_item(self, *args: Any, **kwargs: Any) -> None:
        return None

    def complete_turn(self, *args: Any, **kwargs: Any) -> None:
        return None

    def load_messages(self, public_id: str, user_id: str) -> list[dict[str, Any]]:
        return []


class _NoopMemory:
    async def get_context(self, session_id: str) -> tuple[str | None, list[dict[str, Any]]]:
        return None, []

    async def append_message(self, session_id: str, role: str, content: str) -> bool:
        return False


class _StaticModelClientFactory:
    """Model-client factory fake that returns a fixed assistant message."""

    def __init__(self, reply: str) -> None:
        """Create a static model-client factory."""
        self._reply = reply

    def __call__(self, **kwargs):
        """Return a static model client for attachment tests."""
        _ = kwargs
        reply = self._reply

        class _ModelClient:
            async def sample(self, prompt_envelope) -> ModelStepResult:
                """Return the configured reply for any prompt envelope."""
                _ = prompt_envelope
                return ModelStepResult(
                    assistant_item=AgentMessageItem(text=reply),
                )

        return _ModelClient()


class _NoopUsageService:
    """Usage service fake that accepts quota calls without side effects."""

    def check_quota(self, user_id: str, resource: str, amount: int = 1) -> tuple[bool, str | None]:
        """Allow quota checks during attachment-focused chat turn tests."""
        return True, None

    def consume_quota(self, user_id: str, resource: str, amount: int = 1) -> None:
        """Accept quota consumption without persisting anything."""

    def consume_task(self, user_id: str) -> None:
        """Accept task quota consumption without persisting anything."""

    def record_llm_usage(self, **payload: Any) -> None:
        """Accept LLM usage recording without persisting anything."""


class _FakeFileService:
    def __init__(self, assets: dict[str, FileAsset]) -> None:
        self.assets = assets

    def get_owned_asset(self, *, uploader_public_id: str, file_uuid: str) -> FileAsset:
        return self.assets[file_uuid]

    def create_download_url(self, *, uploader_public_id: str, file_uuid: str) -> str:
        return f"https://files.example.com/{file_uuid}"


def _asset(file_uuid: str, filename: str, content_type: str) -> FileAsset:
    return FileAsset(
        file_uuid=file_uuid,
        original_filename=filename,
        uploader_public_id="user-public-id",
        uploaded_at=datetime.now(UTC),
        deleted_at=None,
        storage_bucket="icore-files",
        object_key=f"files/user-public-id/{file_uuid}",
        storage_etag="etag-123",
        content_type=content_type,
        checksum_sha256="a" * 64,
    )
