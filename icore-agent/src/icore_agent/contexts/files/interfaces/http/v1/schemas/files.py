"""Schemas for the user file asset API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UploadURLRequest(BaseModel):
    """Request body for creating a direct upload URL."""

    original_filename: str = Field(..., min_length=1, max_length=1024)
    content_type: str = Field(..., min_length=1, max_length=255)
    checksum_sha256: str = Field(..., pattern=r"^[0-9a-fA-F]{64}$")
    expires_in: int | None = Field(default=None, ge=1, le=3600)


class UploadURLResponse(BaseModel):
    """Response body containing the direct upload URL."""

    file_uuid: str
    upload_url: str
    expires_in: int


class CompleteUploadRequest(BaseModel):
    """Request body for completing and verifying an upload."""

    checksum_sha256: str = Field(..., pattern=r"^[0-9a-fA-F]{64}$")


class FileAssetResponse(BaseModel):
    """Public file asset metadata response."""

    file_uuid: str
    original_filename: str
    uploader_public_id: str
    uploaded_at: datetime
    deleted_at: datetime | None = None
    storage_bucket: str
    object_key: str
    storage_etag: str | None = None
    content_type: str
    checksum_sha256: str


class DownloadURLResponse(BaseModel):
    """Response body containing a direct download URL."""

    file_uuid: str
    download_url: str
    expires_in: int


class DeleteFileResponse(BaseModel):
    """Response body for soft-deleting a file asset."""

    file_uuid: str
    deleted: bool
