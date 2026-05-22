"""Tests for chat session full-text search."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.responses import StreamingResponse

from icore_agent.application.chat import ChatStreamEvent, ChatTurnResult
from icore_agent.application.chat.history_service import ChatHistoryService
from icore_agent.domain.files import FileAsset
from icore_agent.domain.user import AuthenticatedUser
from icore_agent.interfaces.http.v1.agent.handlers.chat import chat
from icore_agent.interfaces.http.v1.agent.handlers.session import _session_attachment_refs
from icore_agent.interfaces.http.v1.agent.schemas.chat import ChatRequest, ChatResponse


def test_search_user_sessions_empty_query_returns_no_results() -> None:
    """Blank search text should short-circuit without hitting the database."""
    service = ChatHistoryService()
    payload = service.search_user_sessions("user-1", query="   ")
    assert payload == {
        "query": "",
        "sessions": [],
        "total": 0,
        "limit": 20,
        "offset": 0,
    }


def test_search_user_sessions_clamps_pagination() -> None:
    """Search pagination bounds should mirror the list endpoint."""
    service = ChatHistoryService()
    payload = service.search_user_sessions(
        "missing-user",
        query="hello",
        limit=500,
        offset=-3,
    )
    assert payload["limit"] == 100
    assert payload["offset"] == 0
    assert payload["query"] == "hello"
    assert payload["sessions"] == []
    assert payload["total"] == 0


def test_chat_history_preserves_user_message_file_uuid_metadata() -> None:
    """File UUID references should persist with the user message metadata."""
    service = ChatHistoryService()
    session_id = f"session-{uuid4()}"
    user_id = f"user-{uuid4()}"
    file_uuid = str(uuid4())

    service.ensure_owned_session(
        session_id, user_id, title="Use uploaded file")
    service.save_user_message(
        session_id,
        user_id,
        "Summarize this",
        metadata={"file_uuids": [file_uuid]},
    )

    messages = service.load_messages(session_id, user_id)
    assert messages == [
        {
            "role": "user",
            "content": "Summarize this",
            "metadata": {"file_uuids": [file_uuid]},
        }
    ]


def test_session_attachment_refs_resolve_file_uuid_metadata() -> None:
    """Session state should rehydrate file asset references from message metadata."""
    file_uuid = str(uuid4())
    image_uuid = str(uuid4())
    service = FakeFileService({
        file_uuid: _asset(file_uuid, "brief.txt", "text/plain"),
        image_uuid: _asset(image_uuid, "chart.png", "image/png"),
    })

    refs = _session_attachment_refs(
        [
            {
                "role": "user",
                "content": "Use files",
                "metadata": {"file_uuids": [file_uuid, image_uuid, file_uuid]},
            },
            {
                "role": "assistant",
                "content": "Done",
                "metadata": {},
            },
        ],
        user_id="user-public-id",
        file_service=service,
    )

    assert [ref.model_dump(exclude_none=True) for ref in refs] == [
        {
            "file_uuid": file_uuid,
            "original_filename": "brief.txt",
            "filename": "brief.txt",
            "content_type": "text/plain",
            "mode": "file",
        },
        {
            "file_uuid": image_uuid,
            "original_filename": "chart.png",
            "filename": "chart.png",
            "content_type": "image/png",
            "mode": "image",
            "download_url": f"https://files.example.com/{image_uuid}",
        },
    ]


@pytest.mark.asyncio
async def test_chat_stream_starts_without_message_quota_service() -> None:
    """Chat streaming should not depend on message quota checks."""
    service = FakeChatTurnService()
    request = ChatRequest(
        message="Hello",
        session_id="session-1",
        stream=True,
        file_uuids=["file-1", "file-1"],
    )

    response = await chat(
        request,
        user=_auth_user(),
        chat_turn_service=service,
    )

    assert isinstance(response, StreamingResponse)
    assert len(service.commands) == 1
    command = service.commands[0]
    assert command.message == "Hello"
    assert command.session_id == "session-1"
    assert command.stream is True
    assert command.user_id == "user-public-id"
    assert command.user.public_id == "user-public-id"
    assert command.file_uuids == ("file-1", "file-1")


@pytest.mark.asyncio
async def test_chat_non_streaming_returns_service_result() -> None:
    """Non-streaming chat should translate the application result to HTTP schema."""
    service = FakeChatTurnService(reply="plain reply")
    request = ChatRequest(
        message="Hello",
        session_id="session-2",
        stream=False,
    )

    response = await chat(
        request,
        user=_auth_user(),
        chat_turn_service=service,
    )

    assert response == ChatResponse(
        session_id="session-2", reply="plain reply")


class FakeChatTurnService:
    """Application service fake for chat handler tests."""

    def __init__(self, reply: str = "ok") -> None:
        """Create an empty call recorder."""
        self.reply = reply
        self.commands = []

    async def stream(self, command):
        """Record one stream command and return a done-only event stream."""
        self.commands.append(command)
        return self._events()

    async def run(self, command):
        """Record one non-stream command and return a deterministic result."""
        self.commands.append(command)
        return ChatTurnResult(session_id=command.session_id, reply=self.reply)

    async def _events(self):
        """Yield a minimal terminal stream."""
        yield ChatStreamEvent.done()


class FakeFileService:
    """Minimal file asset service fake for session attachment tests."""

    def __init__(self, assets: dict[str, FileAsset]) -> None:
        """Store file assets by UUID."""
        self.assets = assets

    def get_owned_asset(self, *, uploader_public_id: str, file_uuid: str) -> FileAsset:
        """Return one owned test asset."""
        return self.assets[file_uuid]

    def create_download_url(self, *, uploader_public_id: str, file_uuid: str) -> str:
        """Return a deterministic image download URL."""
        return f"https://files.example.com/{file_uuid}"


def _asset(file_uuid: str, filename: str, content_type: str) -> FileAsset:
    """Build a completed file asset for chat history tests."""
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


def _auth_user() -> AuthenticatedUser:
    """Build a domain authenticated user for handler tests."""
    return AuthenticatedUser(
        public_id="user-public-id",
        email="user@example.com",
        name="User One",
        roles=("owner",),
    )
