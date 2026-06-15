"""Attachment metadata loading for agent context assembly."""

from __future__ import annotations

from icore_agent.application.files import FileAssetNotFoundError
from icore_agent.domain.agent.context.models import (
    AgentFileAttachment,
    AgentImageAttachment,
)
from icore_agent.shared.logging.app_logger import get_logger

from .ports import FileContextReader

log = get_logger(__name__)


def load_attachment_context(
    *,
    file_uuids: tuple[str, ...],
    user_id: str,
    file_service: FileContextReader,
) -> tuple[list[AgentImageAttachment], list[AgentFileAttachment]]:
    """Load file UUIDs into compact image and non-image attachment refs."""
    if not file_uuids or not user_id:
        return [], []

    image_refs: list[AgentImageAttachment] = []
    file_refs: list[AgentFileAttachment] = []
    for file_uuid in dedupe_file_uuids(file_uuids):
        try:
            asset = file_service.get_owned_asset(
                uploader_public_id=user_id,
                file_uuid=file_uuid,
            )
            if asset.content_type.startswith("image/"):
                image_refs.append(
                    AgentImageAttachment(
                        filename=asset.original_filename,
                        ref=file_service.create_download_url(
                            uploader_public_id=user_id,
                            file_uuid=file_uuid,
                        ),
                        file_uuid=asset.file_uuid,
                    )
                )
                continue
            file_refs.append(
                AgentFileAttachment(
                    filename=asset.original_filename,
                    file_uuid=asset.file_uuid,
                )
            )
        except FileAssetNotFoundError:
            log.warning(
                "agent_attachment_not_found",
                file_uuid=file_uuid,
                user_id=user_id,
            )
        except Exception as exc:
            log.warning(
                "agent_attachment_context_failed",
                file_uuid=file_uuid,
                error=str(exc),
            )
    return image_refs, file_refs


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
