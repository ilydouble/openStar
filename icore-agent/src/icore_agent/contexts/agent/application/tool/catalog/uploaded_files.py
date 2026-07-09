"""Tools for reading user-uploaded files by attachment UUID."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Protocol

import pandas as pd

from icore_agent.application.files import FileAssetNotFoundError
from icore_agent.application.knowledge.parsers import (
    SUPPORTED_EXTENSIONS,
    parse_file,
)
from icore_agent.config import settings
from icore_agent.domain.files import FileAsset
from icore_agent.shared.logging.app_logger import get_logger

log = get_logger(__name__)

_MAX_READ_BYTES = settings.file_ops_max_size_mb * 1024 * 1024
_MAX_SPREADSHEET_ROWS = 50
_MAX_SPREADSHEET_SHEETS = 5
_SPREADSHEET_EXTENSIONS = {".xlsx", ".xls"}


class UploadedFileReader(Protocol):
    """File operations needed by uploaded-file tools."""

    def get_owned_asset(
        self,
        *,
        uploader_public_id: str,
        file_uuid: str,
    ) -> FileAsset:
        """Return one owned completed file asset."""
        ...

    def read_file_bytes(
        self,
        *,
        uploader_public_id: str,
        file_uuid: str,
    ) -> bytes:
        """Read one owned completed file asset as bytes."""
        ...


def read_uploaded_file(
    *,
    file_service: UploadedFileReader | None,
    user_id: str,
    file_uuid: str,
    encoding: str = "utf-8",
) -> str:
    """Read a user-uploaded file by UUID and return model-readable text."""
    normalized_uuid = str(file_uuid or "").strip()
    if not normalized_uuid:
        return "[ERROR] file_uuid is required."
    if file_service is None or not user_id:
        return "[UNAVAILABLE] Uploaded file access is not configured."

    try:
        asset = file_service.get_owned_asset(
            uploader_public_id=user_id,
            file_uuid=normalized_uuid,
        )
        data = file_service.read_file_bytes(
            uploader_public_id=user_id,
            file_uuid=normalized_uuid,
        )
    except FileAssetNotFoundError:
        return f"[NOT FOUND] Uploaded file {normalized_uuid!r} is unavailable."
    except Exception as exc:
        log.warning(
            "uploaded_file_read_failed",
            file_uuid=normalized_uuid,
            error=str(exc),
        )
        return f"[ERROR] Could not read uploaded file: {exc}"

    if len(data) > _MAX_READ_BYTES:
        return (
            f"[TOO LARGE] File is {len(data) / 1e6:.1f} MB; "
            f"limit is {settings.file_ops_max_size_mb} MB."
        )

    return _render_uploaded_file(asset, data, encoding=encoding)


def _render_uploaded_file(
    asset: FileAsset,
    data: bytes,
    *,
    encoding: str,
) -> str:
    """Render uploaded file bytes into text for the agent tool result."""
    suffix = Path(asset.original_filename).suffix.lower()
    filename = json.dumps(asset.original_filename, ensure_ascii=False)
    file_uuid = json.dumps(asset.file_uuid, ensure_ascii=False)
    header = (
        f"uploaded_file filename={filename} "
        f"uuid={file_uuid}"
    )
    try:
        if suffix in _SPREADSHEET_EXTENSIONS:
            body = _spreadsheet_to_text(data)
        elif suffix == ".csv" or asset.content_type == "text/csv":
            body = data.decode(encoding, errors="replace")
        elif suffix in {".txt", ".md"} or _is_text_content_type(
            asset.content_type,
        ):
            body = data.decode(encoding, errors="replace")
        elif suffix in SUPPORTED_EXTENSIONS:
            body = parse_file(asset.original_filename, data)
        else:
            return (
                f"{header}\n\n[UNSUPPORTED] This uploaded file type "
                f"cannot be rendered as text: {asset.content_type or suffix}"
            )
    except Exception as exc:
        log.warning(
            "uploaded_file_render_failed",
            file_uuid=asset.file_uuid,
            error=str(exc),
        )
        return f"{header}\n\n[ERROR] Could not render uploaded file: {exc}"
    return f"{header}\n\n{body}"


def _spreadsheet_to_text(data: bytes) -> str:
    """Render spreadsheet sheets as bounded CSV previews."""
    excel = pd.ExcelFile(io.BytesIO(data))
    parts: list[str] = []
    for sheet_name in excel.sheet_names[:_MAX_SPREADSHEET_SHEETS]:
        frame = excel.parse(sheet_name=sheet_name, nrows=_MAX_SPREADSHEET_ROWS)
        parts.append(
            f"sheet={sheet_name}\n"
            f"rows_shown={len(frame)}\n"
            f"{frame.to_csv(index=False)}"
        )
    if len(excel.sheet_names) > _MAX_SPREADSHEET_SHEETS:
        omitted = len(excel.sheet_names) - _MAX_SPREADSHEET_SHEETS
        parts.append(f"[OMITTED] {omitted} additional sheets.")
    return "\n\n".join(parts)


def _is_text_content_type(content_type: str) -> bool:
    """Return whether the content type should be decoded as text."""
    return content_type.startswith("text/") or content_type in {
        "application/json",
        "application/xml",
        "application/yaml",
        "application/x-yaml",
    }
