"""HTTP handlers for user file assets."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from icore_agent.application.account import AccountService
from icore_agent.application.files import (
    ChecksumMismatchError,
    FileAssetNotFoundError,
    FileAssetService,
)
from icore_agent.domain.files import FileAsset
from icore_agent.domain.user import AuthenticatedUser

from ...dependencies import account_service, file_asset_service
from ..schemas import (
    CompleteUploadRequest,
    DeleteFileResponse,
    DownloadURLResponse,
    FileAssetResponse,
    UploadURLRequest,
    UploadURLResponse,
)


async def get_files_current_user(
    authorization: str = Header(default=""),
) -> AuthenticatedUser:
    """Resolve the current user for files routes without sync dependency dispatch."""
    try:
        service: AccountService = account_service
        return AuthenticatedUser.from_profile(
            service.get_current_user(authorization)
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


async def get_files_file_asset_service() -> FileAssetService:
    """Return the file asset service for files routes."""
    return file_asset_service


async def create_upload_url(
    payload: UploadURLRequest,
    user: AuthenticatedUser = Depends(get_files_current_user),
    service: FileAssetService = Depends(get_files_file_asset_service),
) -> UploadURLResponse:
    """Create a direct upload URL and pending file asset record."""
    try:
        result = service.create_upload_url(
            uploader_public_id=user.public_id,
            original_filename=payload.original_filename,
            content_type=payload.content_type,
            checksum_sha256=payload.checksum_sha256,
            expires_in=payload.expires_in,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UploadURLResponse(
        file_uuid=result.file_uuid,
        upload_url=result.upload_url,
        expires_in=result.expires_in,
    )


async def complete_upload(
    file_uuid: str,
    payload: CompleteUploadRequest,
    user: AuthenticatedUser = Depends(get_files_current_user),
    service: FileAssetService = Depends(get_files_file_asset_service),
) -> FileAssetResponse:
    """Verify a direct upload and mark the file asset completed."""
    try:
        asset = service.complete_upload(
            uploader_public_id=user.public_id,
            file_uuid=file_uuid,
            checksum_sha256=payload.checksum_sha256,
        )
    except ChecksumMismatchError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileAssetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_asset(asset)


async def create_download_url(
    file_uuid: str,
    user: AuthenticatedUser = Depends(get_files_current_user),
    service: FileAssetService = Depends(get_files_file_asset_service),
) -> DownloadURLResponse:
    """Create a direct download URL for an owned file asset."""
    expires_in = service.default_expires_in
    try:
        download_url = service.create_download_url(
            uploader_public_id=user.public_id,
            file_uuid=file_uuid,
            expires_in=expires_in,
        )
    except FileAssetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc
    return DownloadURLResponse(
        file_uuid=file_uuid,
        download_url=download_url,
        expires_in=expires_in,
    )


async def delete_file(
    file_uuid: str,
    user: AuthenticatedUser = Depends(get_files_current_user),
    service: FileAssetService = Depends(get_files_file_asset_service),
) -> DeleteFileResponse:
    """Soft-delete an owned file asset."""
    try:
        asset = service.delete_file(
            uploader_public_id=user.public_id,
            file_uuid=file_uuid,
        )
    except FileAssetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc
    return DeleteFileResponse(
        file_uuid=asset.file_uuid,
        deleted=asset.deleted_at is not None,
    )


def _serialize_asset(asset: FileAsset) -> FileAssetResponse:
    """Serialize domain file asset metadata for HTTP responses."""
    return FileAssetResponse(
        file_uuid=asset.file_uuid,
        original_filename=asset.original_filename,
        uploader_public_id=asset.uploader_public_id,
        uploaded_at=asset.uploaded_at,
        deleted_at=asset.deleted_at,
        storage_bucket=asset.storage_bucket,
        object_key=asset.object_key,
        storage_etag=asset.storage_etag,
        content_type=asset.content_type,
        checksum_sha256=asset.checksum_sha256,
    )
