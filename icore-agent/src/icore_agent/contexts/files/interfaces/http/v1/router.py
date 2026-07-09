"""Files API router."""

from fastapi import APIRouter

from icore_agent.interfaces.http.v1.envelope import ApiEnvelopeRoute
from .handlers import (
    complete_upload,
    create_download_url,
    create_upload_url,
    delete_file,
)
from .schemas import (
    DeleteFileResponse,
    DownloadURLResponse,
    FileAssetResponse,
    UploadURLResponse,
)

router = APIRouter(
    prefix="/api/v1/files",
    tags=["files"],
    route_class=ApiEnvelopeRoute,
)

router.post(
    "/upload-url/",
    response_model=UploadURLResponse,
    summary="Create a direct upload URL for a user file asset",
)(create_upload_url)
router.post(
    "/{file_uuid}/complete/",
    response_model=FileAssetResponse,
    summary="Verify a direct upload and complete a file asset",
)(complete_upload)
router.get(
    "/{file_uuid}/download-url/",
    response_model=DownloadURLResponse,
    summary="Create a direct download URL for a user file asset",
)(create_download_url)
router.delete(
    "/{file_uuid}/",
    response_model=DeleteFileResponse,
    summary="Soft-delete a user file asset",
)(delete_file)
