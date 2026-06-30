"""Pi Agent uploaded-project workspace API router."""

from fastapi import APIRouter

from ..envelope import ApiEnvelopeRoute
from .handlers import (
    complete_workspace_upload,
    create_workspace_upload_url,
    delete_workspace,
    download_pi_workspace,
    get_workspace,
    list_pi_changes,
    list_workspaces,
    save_all_pi_changes,
    undo_pi_change,
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

# ---- Pi session file-change actions (Undo / Save All) ----
# These proxy directly to pi-source-service and are session-scoped, not
# workspace-scoped — the pi_session_id ties them to the right agent instance.

router.post(
    "/sessions/{pi_session_id}/changes/{change_id}/undo",
    summary="Undo a single Pi Agent file change (git revert)",
)(undo_pi_change)

router.post(
    "/sessions/{pi_session_id}/save-all",
    summary="Mark all pending Pi Agent file changes as permanently saved",
)(save_all_pi_changes)

router.get(
    "/sessions/{pi_session_id}/changes",
    summary="List pending Pi Agent file changes for a session",
)(list_pi_changes)

# Download returns application/zip — ApiEnvelopeRoute only wraps
# application/json responses (_should_wrap check), so this passes through.
router.get(
    "/sessions/{pi_session_id}/download",
    summary="Download the Pi Agent session workspace as a ZIP archive",
)(download_pi_workspace)
