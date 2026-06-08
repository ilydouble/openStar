"""HTTP handlers for Pi Agent uploaded-project workspaces."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, Header, HTTPException

from icore_agent.application.account import AccountService
from icore_agent.application.pi_workspaces import (
    ChecksumMismatchError,
    PiWorkspaceService,
    UnsafeArchiveError,
    WorkspaceLimitExceededError,
    WorkspaceNotFoundError,
)
from icore_agent.domain.user import AuthenticatedUser

from ...dependencies import account_service, pi_workspace_service
from ..schemas import (
    CompleteWorkspaceUploadRequest,
    DeleteWorkspaceResponse,
    WorkspaceListResponse,
    WorkspaceResponse,
    WorkspaceUploadURLRequest,
    WorkspaceUploadURLResponse,
)


async def get_pi_workspaces_current_user(
    authorization: str = Header(default=""),
) -> AuthenticatedUser:
    """Resolve the current user for Pi workspace routes without sync dependency dispatch."""
    try:
        service: AccountService = account_service
        return AuthenticatedUser.from_profile(
            service.get_current_user(authorization)
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


async def get_pi_workspaces_service() -> PiWorkspaceService:
    """Return the Pi workspace service for Pi workspace routes."""
    return pi_workspace_service


async def create_workspace_upload_url(
    payload: WorkspaceUploadURLRequest,
    user: AuthenticatedUser = Depends(get_pi_workspaces_current_user),
    service: PiWorkspaceService = Depends(get_pi_workspaces_service),
) -> WorkspaceUploadURLResponse:
    """Register a pending workspace and return a presigned archive upload URL."""
    try:
        result = service.create_upload_url(
            owner_user_id=user.public_id,
            title=payload.title,
            checksum_sha256=payload.checksum_sha256,
            expires_in=payload.expires_in,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WorkspaceUploadURLResponse(
        workspace_id=result.workspace_id,
        upload_url=result.upload_url,
        expires_in=result.expires_in,
    )


async def complete_workspace_upload(
    workspace_id: str,
    payload: CompleteWorkspaceUploadRequest,
    user: AuthenticatedUser = Depends(get_pi_workspaces_current_user),
    service: PiWorkspaceService = Depends(get_pi_workspaces_service),
) -> WorkspaceResponse:
    """Verify an uploaded archive and mark the workspace ready for Pi Agent use."""
    try:
        workspace = service.complete_upload(
            owner_user_id=user.public_id,
            workspace_id=workspace_id,
            checksum_sha256=payload.checksum_sha256,
        )
    except ChecksumMismatchError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (WorkspaceLimitExceededError, UnsafeArchiveError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workspace not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_workspace(workspace)


async def list_workspaces(
    user: AuthenticatedUser = Depends(get_pi_workspaces_current_user),
    service: PiWorkspaceService = Depends(get_pi_workspaces_service),
) -> WorkspaceListResponse:
    """List the caller's own Pi Agent project workspaces, most recent first."""
    workspaces = service.list_workspaces(owner_user_id=user.public_id)
    return WorkspaceListResponse(
        workspaces=[_serialize_workspace(item) for item in workspaces]
    )


async def get_workspace(
    workspace_id: str,
    user: AuthenticatedUser = Depends(get_pi_workspaces_current_user),
    service: PiWorkspaceService = Depends(get_pi_workspaces_service),
) -> WorkspaceResponse:
    """Return one Pi workspace owned by the caller."""
    try:
        workspace = service.get_owned_workspace(
            owner_user_id=user.public_id,
            workspace_id=workspace_id,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workspace not found") from exc
    return _serialize_workspace(workspace)


async def delete_workspace(
    workspace_id: str,
    user: AuthenticatedUser = Depends(get_pi_workspaces_current_user),
    service: PiWorkspaceService = Depends(get_pi_workspaces_service),
) -> DeleteWorkspaceResponse:
    """Soft-delete an owned Pi workspace and remove its stored archive."""
    try:
        service.delete_workspace(owner_user_id=user.public_id, workspace_id=workspace_id)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workspace not found") from exc
    return DeleteWorkspaceResponse(id=workspace_id, deleted=True)


def _serialize_workspace(workspace: dict[str, Any]) -> WorkspaceResponse:
    """Serialize a workspace metadata dict for HTTP responses."""
    return WorkspaceResponse(
        id=workspace["id"],
        title=workspace["title"],
        status=workspace["status"],
        size_bytes=workspace["size_bytes"],
        file_count=workspace["file_count"],
        created_at=workspace["created_at"],
        updated_at=workspace["updated_at"],
    )
