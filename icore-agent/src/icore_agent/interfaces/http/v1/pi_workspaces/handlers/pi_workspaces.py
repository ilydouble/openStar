"""HTTP handlers for Pi Agent uploaded-project workspaces."""

from __future__ import annotations

from typing import Any, AsyncIterator

import httpx
from fastapi import Depends, Header, HTTPException
from fastapi.responses import StreamingResponse

from icore_agent.config import settings

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


async def undo_pi_change(
    pi_session_id: str,
    change_id: str,
    user: AuthenticatedUser = Depends(get_pi_workspaces_current_user),
) -> dict[str, Any]:
    """Proxy an undo request to pi-source-service for a single file change.

    Reverts the specific commit identified by `change_id` inside the session's
    sandbox workspace using `git checkout <parentHash> -- <file>` followed by
    a new revert commit. The frontend receives the git commit hash of the
    undo operation so it can confirm the action completed.
    """
    url = f"{settings.pi_service_url}/v1/session/{pi_session_id}/undo/{change_id}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=exc.response.text,
            ) from exc
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"pi-service unreachable: {exc}") from exc


async def save_all_pi_changes(
    pi_session_id: str,
    user: AuthenticatedUser = Depends(get_pi_workspaces_current_user),
) -> dict[str, Any]:
    """Proxy a save-all request to pi-source-service.

    Marks all pending (undoable) file changes in the session as permanently
    saved. After this call the frontend should hide Undo buttons for all
    changes recorded before this point.
    """
    url = f"{settings.pi_service_url}/v1/session/{pi_session_id}/save-all"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=exc.response.text,
            ) from exc
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"pi-service unreachable: {exc}") from exc


async def list_pi_changes(
    pi_session_id: str,
    user: AuthenticatedUser = Depends(get_pi_workspaces_current_user),
) -> dict[str, Any]:
    """List all pending file changes for a Pi session.

    Returns the same ``{ changes: [...] }`` payload that pi-source-service
    exposes at ``GET /v1/session/{id}/changes``.  Returns an empty list when
    the session no longer exists on the pi-service side (e.g. after a restart
    or TTL expiry) so the frontend can degrade gracefully.
    """
    url = f"{settings.pi_service_url}/v1/session/{pi_session_id}/changes"
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(url)
            if resp.status_code == 404:
                return {"changes": []}
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=exc.response.text,
            ) from exc
        except httpx.RequestError:
            # pi-service unreachable — return empty rather than error so page
            # load succeeds even if pi-service is temporarily down.
            return {"changes": []}


async def download_pi_workspace(
    pi_session_id: str,
    user: AuthenticatedUser = Depends(get_pi_workspaces_current_user),
) -> StreamingResponse:
    """Stream the Pi session workspace as a ZIP archive for the user to download.

    Proxies ``GET /v1/session/{id}/download`` from pi-source-service and
    forwards the ZIP stream directly to the browser.  The .git directory is
    excluded by pi-source-service so the user receives clean project files.
    """
    url = f"{settings.pi_service_url}/v1/session/{pi_session_id}/download"

    async def _stream_zip() -> AsyncIterator[bytes]:
        # Keep the httpx client alive for the full duration of the streaming
        # response — the generator holds the context open until exhausted.
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream("GET", url) as resp:
                if resp.status_code == 404:
                    raise HTTPException(status_code=404, detail="Session not found")
                if resp.status_code != 200:
                    raise HTTPException(
                        status_code=502,
                        detail=f"pi-service returned {resp.status_code}",
                    )
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    yield chunk

    return StreamingResponse(
        _stream_zip(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="pi-workspace-{pi_session_id}.zip"'
        },
    )


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
