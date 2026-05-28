"""Context loading for chat turn workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from icore_agent.application.files import FileAssetNotFoundError, FileAssetService
from icore_agent.application.knowledge.parsers import parse_file
from icore_agent.application.memory import UserMemoryService
from icore_agent.domain.memory import TurnMemoryContext
from icore_agent.shared.logging.app_logger import get_logger

from .services.history_service import ChatHistoryService

log = get_logger(__name__)

ChatHistoryMessage = dict[str, Any]


class ConversationMemory(Protocol):
    """Conversation cache operations used by chat turn workflows."""

    async def get_context(
        self,
        session_id: str,
    ) -> tuple[str | None, list[ChatHistoryMessage]]:
        """Return a cached summary and recent messages."""
        ...

    async def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> bool:
        """Append one message to the cached conversation."""
        ...


@dataclass(frozen=True, slots=True)
class ChatImageAttachment:
    """Image attachment reference passed from file assets into chat context."""

    filename: str
    ref: str
    file_uuid: str

    def to_orchestrator_payload(self) -> dict[str, Any]:
        """Return the dict shape consumed by the engine orchestrator."""
        return {
            "filename": self.filename,
            "ref": self.ref,
            "file_uuid": self.file_uuid,
        }


@dataclass(frozen=True, slots=True)
class ChatDataColumn:
    """Column preview metadata for one uploaded data file."""

    name: str
    dtype: str

    def to_orchestrator_payload(self) -> dict[str, str]:
        """Return the dict shape consumed by the engine orchestrator."""
        return {"name": self.name, "dtype": self.dtype}


@dataclass(frozen=True, slots=True)
class ChatDataAttachment:
    """Structured data attachment reference passed into chat context."""

    filename: str
    file_uuid: str
    abs_path: str
    columns: tuple[ChatDataColumn, ...] = ()
    row_count: int | None = None
    preview_md: str = ""
    preview_error: str = ""

    def to_orchestrator_payload(self) -> dict[str, Any]:
        """Return the dict shape consumed by the engine orchestrator."""
        return {
            "filename": self.filename,
            "file_uuid": self.file_uuid,
            "abs_path": self.abs_path,
            "columns": [
                column.to_orchestrator_payload()
                for column in self.columns
            ],
            "row_count": self.row_count,
            "preview_md": self.preview_md,
            "preview_error": self.preview_error,
        }


@dataclass(frozen=True, slots=True)
class ChatContext:
    """Loaded prompt context for one chat turn."""

    summary: str | None
    strands_history: list[dict[str, Any]]
    attachments_text: str | None
    has_rag: bool
    image_attachments: list[ChatImageAttachment]
    data_attachments: list[ChatDataAttachment]
    user_memory_prompt: str | None = None

    @property
    def has_attachments(self) -> bool:
        """Return whether file or RAG context should enable tools."""
        return bool(
            self.has_rag
            or self.image_attachments
            or self.data_attachments
        )

    @property
    def image_attachment_payloads(self) -> list[dict[str, Any]]:
        """Return image attachments in the engine orchestrator dict shape."""
        return [
            attachment.to_orchestrator_payload()
            for attachment in self.image_attachments
        ]

    @property
    def data_attachment_payloads(self) -> list[dict[str, Any]]:
        """Return data attachments in the engine orchestrator dict shape."""
        return [
            attachment.to_orchestrator_payload()
            for attachment in self.data_attachments
        ]


async def load_chat_context(
    *,
    session_id: str,
    file_uuids: tuple[str, ...],
    user_id: str,
    user_message: str = "",
    agent_hint: str | None = None,
    incognito: bool = False,
    file_service: FileAssetService,
    chat_history: ChatHistoryService,
    conversation_memory: ConversationMemory,
    user_memory_service: UserMemoryService | None = None,
) -> ChatContext:
    """Load cached history, durable history fallback, and UUID-addressed files."""
    try:
        summary, history = await conversation_memory.get_context(session_id)
    except Exception as exc:
        log.warning("load_context_fallback",
                    session_id=session_id, error=str(exc))
        return _empty_context()

    if not history and not incognito:
        try:
            history = chat_history.load_messages(session_id, user_id)
        except (PermissionError, LookupError):
            history = []

    inline_text, image_refs, data_refs = load_file_context(
        file_uuids=file_uuids,
        user_id=user_id,
        file_service=file_service,
    )
    user_memory_prompt = None
    if user_memory_service is not None and not incognito:
        user_memory_prompt = user_memory_service.build_memory_prompt(
            user_id,
            TurnMemoryContext(
                message=user_message,
                session_summary=summary or None,
                agent_hint=agent_hint,
            ),
        )
    return ChatContext(
        summary=summary or None,
        strands_history=to_strands_messages(history),
        attachments_text=inline_text or None,
        has_rag=False,
        image_attachments=image_refs,
        data_attachments=data_refs,
        user_memory_prompt=user_memory_prompt,
    )


def load_file_context(
    *,
    file_uuids: tuple[str, ...],
    user_id: str,
    file_service: FileAssetService,
) -> tuple[str | None, list[ChatImageAttachment], list[ChatDataAttachment]]:
    """Load file UUIDs into text, image, and data-agent context buckets."""
    if not file_uuids or not user_id:
        return None, [], []

    inline_parts: list[str] = []
    image_refs: list[ChatImageAttachment] = []
    data_refs: list[ChatDataAttachment] = []
    for file_uuid in dedupe_file_uuids(file_uuids):
        try:
            asset = file_service.get_owned_asset(
                uploader_public_id=user_id,
                file_uuid=file_uuid,
            )
            if asset.content_type.startswith("image/"):
                image_refs.append(ChatImageAttachment(
                    filename=asset.original_filename,
                    ref=file_service.create_download_url(
                        uploader_public_id=user_id,
                        file_uuid=file_uuid,
                    ),
                    file_uuid=asset.file_uuid,
                ))
                continue
            if is_data_file(asset.original_filename, asset.content_type):
                data_refs.append(materialize_data_ref(
                    file_service=file_service,
                    user_id=user_id,
                    file_uuid=file_uuid,
                ))
                continue
            content = parse_file(
                asset.original_filename,
                file_service.read_file_bytes(
                    uploader_public_id=user_id,
                    file_uuid=file_uuid,
                ),
            )
            inline_parts.append(
                f"### {asset.original_filename} ({asset.file_uuid})\n\n{content}"
            )
        except FileAssetNotFoundError:
            log.warning("chat_file_not_found",
                        file_uuid=file_uuid, user_id=user_id)
        except Exception as exc:
            log.warning("chat_file_context_failed",
                        file_uuid=file_uuid, error=str(exc))
    inline_text = "\n\n".join(inline_parts) if inline_parts else None
    return inline_text, image_refs, data_refs


def dedupe_file_uuids(file_uuids: tuple[str, ...]) -> tuple[str, ...]:
    """Return file UUIDs in first-seen order without duplicates."""
    seen: set[str] = set()
    ordered: list[str] = []
    for file_uuid in file_uuids:
        normalized = str(file_uuid).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)
    return tuple(ordered)


def to_strands_messages(history: list[ChatHistoryMessage]) -> list[dict[str, Any]]:
    """Convert cached or persisted messages to Strands message format."""
    return [
        {
            "role": message["role"],
            "content": [
                {"type": "text", "text": message["content"]}
            ],
        }
        for message in history
        if message.get("role") in ("user", "assistant")
        and message.get("content")
    ]


def is_data_file(filename: str, content_type: str) -> bool:
    """Return whether a file should be routed to the data agent."""
    suffix = Path(filename).suffix.lower()
    return suffix in {".csv", ".xlsx", ".xls"} or content_type in {
        "text/csv",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }


def materialize_data_ref(
    *,
    file_service: FileAssetService,
    user_id: str,
    file_uuid: str,
) -> ChatDataAttachment:
    """Create a local temp copy for data-agent tools and collect preview metadata."""
    asset, path = file_service.materialize_temp_file(
        uploader_public_id=user_id,
        file_uuid=file_uuid,
    )
    columns: tuple[ChatDataColumn, ...] = ()
    row_count: int | None = None
    preview_md = ""
    preview_error = ""
    try:
        frame = pd.read_csv(path) if path.suffix.lower(
        ) == ".csv" else pd.read_excel(path)
        row_count = int(len(frame))
        columns = tuple(
            ChatDataColumn(name=str(name), dtype=str(dtype))
            for name, dtype in frame.dtypes.items()
        )
        preview_md = frame.head(10).to_markdown(index=False)
    except Exception as exc:
        preview_error = str(exc)
    return ChatDataAttachment(
        filename=asset.original_filename,
        file_uuid=asset.file_uuid,
        abs_path=str(path),
        columns=columns,
        row_count=row_count,
        preview_md=preview_md,
        preview_error=preview_error,
    )


def _empty_context() -> ChatContext:
    """Return an empty context after a cache loading failure."""
    return ChatContext(
        summary=None,
        strands_history=[],
        attachments_text=None,
        has_rag=False,
        image_attachments=[],
        data_attachments=[],
        user_memory_prompt=None,
    )
