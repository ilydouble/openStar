from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from icore_agent.contexts.files.domain import FileAsset
from icore_agent.contexts.account.domain.user import AuthenticatedUser
from icore_agent.contexts.files.interfaces.http.v1.handlers.files import (
    get_files_current_user,
    get_files_file_asset_service,
)
from icore_agent.interfaces.http.v1.router import include_api_routers


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    """Clear dependency overrides around each API test."""
    yield


def _build_app() -> FastAPI:
    """Build a router-only test app without global auth middleware."""
    test_app = FastAPI()
    include_api_routers(test_app)
    return test_app


def _api_data(resp) -> dict:
    """Return the ApiEnvelope data object from a test response."""
    payload = resp.json()
    assert payload["code"] == resp.status_code
    assert payload["message"]
    assert payload["timestamp"]
    return payload["data"]


class FakeFileAssetService:
    """Fake application service for file API contract tests."""

    def __init__(self) -> None:
        """Initialize deterministic API responses."""
        self.default_expires_in = 600
        self.asset = FileAsset(
            file_uuid=str(uuid4()),
            original_filename="brief.txt",
            uploader_public_id="",
            uploaded_at=datetime.now(UTC),
            deleted_at=None,
            storage_bucket="icore-files",
            object_key="files/user/asset",
            storage_etag="etag-123",
            content_type="text/plain",
            checksum_sha256="a" * 64,
        )

    def create_upload_url(self, **kwargs):
        """Return a deterministic upload URL result."""
        self.asset = FileAsset(
            file_uuid=self.asset.file_uuid,
            original_filename=kwargs["original_filename"],
            uploader_public_id=kwargs["uploader_public_id"],
            uploaded_at=self.asset.uploaded_at,
            deleted_at=None,
            storage_bucket="icore-files",
            object_key=f"files/{kwargs['uploader_public_id']}/{self.asset.file_uuid}",
            storage_etag=None,
            content_type=kwargs["content_type"],
            checksum_sha256=kwargs["checksum_sha256"],
        )

        class Result:
            file_uuid = self.asset.file_uuid
            upload_url = "https://storage.example.com/upload"
            expires_in = 600

        return Result()

    def complete_upload(self, **kwargs):
        """Return the completed asset."""
        self.asset = self.asset.mark_completed(
            storage_etag="etag-123",
            content_type=self.asset.content_type,
        )
        return self.asset

    def create_download_url(self, **kwargs) -> str:
        """Return a deterministic download URL."""
        return "https://storage.example.com/download"

    def delete_file(self, **kwargs):
        """Return a soft-deleted asset."""
        self.asset = self.asset.mark_deleted(datetime.now(UTC))
        return self.asset


@pytest.mark.asyncio
async def test_files_upload_url_requires_auth() -> None:
    """The files upload URL endpoint should be protected."""
    test_app = _build_app()
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/api/v1/files/upload-url/",
            json={
                "original_filename": "brief.txt",
                "content_type": "text/plain",
                "checksum_sha256": "a" * 64,
            },
        )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_files_upload_complete_download_and_delete_flow() -> None:
    """The files API should expose UUID-based asset operations."""
    test_app = _build_app()
    fake_service = FakeFileAssetService()

    async def fake_current_user() -> AuthenticatedUser:
        """Return the current test user."""
        return AuthenticatedUser(
            public_id="user-public-id",
            email="user@example.com",
            name="User One",
            roles=("owner",),
        )

    async def fake_file_asset_service() -> FakeFileAssetService:
        """Return the fake file asset service."""
        return fake_service

    test_app.dependency_overrides[get_files_current_user] = fake_current_user
    test_app.dependency_overrides[get_files_file_asset_service] = fake_file_asset_service
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        upload = await client.post(
            "/api/v1/files/upload-url/",
            json={
                "original_filename": "brief.txt",
                "content_type": "text/plain",
                "checksum_sha256": "a" * 64,
            },
        )
        assert upload.status_code == 200, upload.text
        upload_body = _api_data(upload)
        assert upload_body["file_uuid"] == fake_service.asset.file_uuid
        assert upload_body["upload_url"] == "https://storage.example.com/upload"
        assert upload_body["expires_in"] == 600

        complete = await client.post(
            f"/api/v1/files/{upload_body['file_uuid']}/complete/",
            json={"checksum_sha256": "a" * 64},
        )
        assert complete.status_code == 200, complete.text
        assert _api_data(complete)["storage_etag"] == "etag-123"

        download = await client.get(
            f"/api/v1/files/{upload_body['file_uuid']}/download-url/",
        )
        assert download.status_code == 200, download.text
        assert _api_data(download)[
            "download_url"] == "https://storage.example.com/download"

        deleted = await client.delete(
            f"/api/v1/files/{upload_body['file_uuid']}/",
        )
        assert deleted.status_code == 200, deleted.text
        assert _api_data(deleted)["deleted"] is True


@pytest.mark.asyncio
async def test_legacy_agent_attach_routes_are_removed() -> None:
    """Legacy agent attachment upload routes should no longer be registered."""
    test_app = _build_app()
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        assert (await client.post("/api/v1/agent/attach")).status_code == 404
        assert (await client.post("/api/v1/agent/attach/image")).status_code == 404
        assert (await client.post("/api/v1/agent/attach/data")).status_code == 404
        assert (await client.get("/api/v1/agent/attachments/session-1")).status_code == 404
