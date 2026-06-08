"""Attachment loading for agent context assembly."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from icore_agent.application.files import FileAssetNotFoundError
from icore_agent.application.knowledge.parsers import parse_file
from icore_agent.shared.logging.app_logger import get_logger

from .models import AgentDataAttachment, AgentDataColumn, AgentImageAttachment
from .ports import FileContextReader

log = get_logger(__name__)


def load_attachment_context(
    *,
    file_uuids: tuple[str, ...],
    user_id: str,
    file_service: FileContextReader,
) -> tuple[str | None, list[AgentImageAttachment], list[AgentDataAttachment]]:
    """Load file UUIDs into text, image, and data-agent context buckets."""
    if not file_uuids or not user_id:
        return None, [], []

    inline_parts: list[str] = []
    image_refs: list[AgentImageAttachment] = []
    data_refs: list[AgentDataAttachment] = []
    for file_uuid in dedupe_file_uuids(file_uuids):
        try:
            asset = file_service.get_owned_asset(
                uploader_public_id=user_id,
                file_uuid=file_uuid,
            )
            if asset.content_type.startswith("image/"):
                image_refs.append(AgentImageAttachment(
                    filename=asset.original_filename,
                    ref=file_service.create_download_url(
                        uploader_public_id=user_id,
                        file_uuid=file_uuid,
                    ),
                    file_uuid=asset.file_uuid,
                ))
                continue
            if is_data_file(asset.original_filename, asset.content_type):
                data_refs.append(materialize_data_attachment(
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


def is_data_file(filename: str, content_type: str) -> bool:
    """Return whether a file should be routed to the data agent."""
    suffix = Path(filename).suffix.lower()
    return suffix in {".csv", ".xlsx", ".xls"} or content_type in {
        "text/csv",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }


def materialize_data_attachment(
    *,
    file_service: FileContextReader,
    user_id: str,
    file_uuid: str,
) -> AgentDataAttachment:
    """Create a local temp copy for data-agent tools and collect preview metadata."""
    asset, path = file_service.materialize_temp_file(
        uploader_public_id=user_id,
        file_uuid=file_uuid,
    )
    columns: tuple[AgentDataColumn, ...] = ()
    row_count: int | None = None
    preview_md = ""
    preview_error = ""
    try:
        frame = pd.read_csv(path) if path.suffix.lower(
        ) == ".csv" else pd.read_excel(path)
        row_count = int(len(frame))
        columns = tuple(
            AgentDataColumn(name=str(name), dtype=str(dtype))
            for name, dtype in frame.dtypes.items()
        )
        preview_md = frame.head(10).to_markdown(index=False)
    except Exception as exc:
        preview_error = str(exc)
    return AgentDataAttachment(
        filename=asset.original_filename,
        file_uuid=asset.file_uuid,
        abs_path=str(path),
        columns=columns,
        row_count=row_count,
        preview_md=preview_md,
        preview_error=preview_error,
    )
