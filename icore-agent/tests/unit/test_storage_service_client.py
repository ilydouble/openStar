from __future__ import annotations

import httpx

from icore_agent.infrastructure.storage.storage_service_client import (
    StorageServiceClient,
)


def test_storage_service_client_unwraps_api_envelope(monkeypatch) -> None:
    """Storage-service JSON responses should be read from the ApiEnvelope data field."""
    posts: list[dict] = []

    class FakeHTTPClient:
        """Small httpx.Client fake that returns a storage-service ApiEnvelope."""

        def __init__(self, *, timeout: float) -> None:
            """Capture the configured timeout."""
            self.timeout = timeout

        def __enter__(self) -> "FakeHTTPClient":
            """Enter the fake context manager."""
            return self

        def __exit__(self, *args) -> None:
            """Exit the fake context manager."""

        def post(self, url: str, json: dict, headers: dict) -> httpx.Response:
            """Return a successful ApiEnvelope response for presign requests."""
            posts.append({"url": url, "json": json, "headers": headers})
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "message": "操作成功",
                    "data": {"url": "https://storage.example.com/upload"},
                    "timestamp": "2026-05-21T14:30:00Z",
                },
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(httpx, "Client", FakeHTTPClient)
    client = StorageServiceClient(
        base_url="http://storage-service:8090",
        token="secret-token",
        timeout=30,
    )

    upload_url = client.presign_put(
        bucket="icore-files",
        object_key="files/user/file",
        content_type="text/plain",
        expires_in=600,
    )

    assert upload_url == "https://storage.example.com/upload"
    assert posts[0]["url"] == "http://storage-service:8090/presign/put"
    assert posts[0]["headers"] == {"X-Storage-Service-Token": "secret-token"}
