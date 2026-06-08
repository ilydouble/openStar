"""Schemas for the Pi Agent uploaded-project workspace API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WorkspaceUploadURLRequest(BaseModel):
    """Request body for creating a presigned workspace-archive upload URL."""

    title: str = Field(..., min_length=1, max_length=200)
    checksum_sha256: str = Field(..., pattern=r"^[0-9a-fA-F]{64}$")
    expires_in: int | None = Field(default=None, ge=1, le=3600)


class WorkspaceUploadURLResponse(BaseModel):
    """Response body containing the presigned workspace-archive upload URL."""

    workspace_id: str
    upload_url: str
    expires_in: int


class CompleteWorkspaceUploadRequest(BaseModel):
    """Request body for completing and verifying a workspace-archive upload."""

    checksum_sha256: str = Field(..., pattern=r"^[0-9a-fA-F]{64}$")


class WorkspaceResponse(BaseModel):
    """Public Pi workspace metadata response."""

    id: str
    title: str
    status: str
    size_bytes: int
    file_count: int
    created_at: int
    updated_at: int


class WorkspaceListResponse(BaseModel):
    """Response body listing one user's Pi workspaces."""

    workspaces: list[WorkspaceResponse]


class DeleteWorkspaceResponse(BaseModel):
    """Response body for soft-deleting a Pi workspace."""

    id: str
    deleted: bool
