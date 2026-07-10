"""Tests for session attachment HTTP projections."""

from datetime import UTC, datetime
from uuid import uuid4

from icore_agent.contexts.agent.interfaces.http.v1.handlers.session import (
    _asset_mode,
    _session_attachment_refs,
)
from icore_agent.contexts.files.domain.models import FileAsset


def test_asset_mode_classifies_supported_document_types_as_data() -> None:
    """Document uploads should map to the frontend data attachment mode."""
    assert _asset_mode("report.pdf", "application/pdf") == "data"
    assert _asset_mode(
        "notes.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ) == "data"
    assert _asset_mode("readme.md", "text/markdown") == "data"
    assert _asset_mode("photo.png", "image/png") == "image"


def test_session_attachment_refs_include_pdf_as_data_mode() -> None:
    """PDF assets should resolve into session attachment refs for UI hydration."""
    file_uuid = str(uuid4())
    service = FakeFileService({
        file_uuid: _asset(file_uuid, "report.pdf", "application/pdf"),
    })

    refs = _session_attachment_refs(
        [{
            "items": [{
                "type": "user_message",
                "metadata": {"file_uuids": [file_uuid]},
            }],
        }],
        user_id="user-public-id",
        file_service=service,
    )

    assert len(refs) == 1
    assert refs[0].mode == "data"
    assert refs[0].original_filename == "report.pdf"


class FakeFileService:
    """Minimal file service fake for attachment projection tests."""

    def __init__(self, assets: dict[str, FileAsset]) -> None:
        """Store assets by public file UUID."""
        self.assets = assets

    def get_owned_asset(
        self,
        *,
        uploader_public_id: str,
        file_uuid: str,
    ) -> FileAsset:
        """Return the requested owned asset."""
        return self.assets[file_uuid]

    def create_download_url(
        self,
        *,
        uploader_public_id: str,
        file_uuid: str,
    ) -> str:
        """Return a deterministic download URL."""
        return f"https://files.example.com/{file_uuid}"


def _asset(file_uuid: str, filename: str, content_type: str) -> FileAsset:
    """Build a completed test file asset."""
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
