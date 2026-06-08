"""Pi Agent uploaded-project workspace API router."""

from fastapi import APIRouter

from ..envelope import ApiEnvelopeRoute
from .handlers import (
    complete_workspace_upload,
    create_workspace_upload_url,
    delete_workspace,
    get_workspace,
    list_workspaces,
)
from .schemas import (
    DeleteWorkspaceResponse,
    WorkspaceListResponse,
    WorkspaceResponse,
    WorkspaceUploadURLResponse,
)

router = APIRouter(
    prefix="/api/v1/pi/workspaces",
    tags=["pi-workspaces"],
    route_class=ApiEnvelopeRoute,
)

router.post(
    "/upload-url/",
    response_model=WorkspaceUploadURLResponse,
    summary="Create a presigned upload URL for a Pi Agent project archive",
)(create_workspace_upload_url)
router.post(
    "/{workspace_id}/complete/",
    response_model=WorkspaceResponse,
    summary="Verify an uploaded project archive and mark the workspace ready",
)(complete_workspace_upload)
router.get(
    "/",
    response_model=WorkspaceListResponse,
    summary="List the caller's own Pi Agent project workspaces",
)(list_workspaces)
router.get(
    "/{workspace_id}/",
    response_model=WorkspaceResponse,
    summary="Get one Pi Agent project workspace owned by the caller",
)(get_workspace)
router.delete(
    "/{workspace_id}/",
    response_model=DeleteWorkspaceResponse,
    summary="Soft-delete an owned Pi Agent project workspace",
)(delete_workspace)
