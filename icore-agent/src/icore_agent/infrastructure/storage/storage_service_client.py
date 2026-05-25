"""Synchronous client for the internal storage-service."""

from __future__ import annotations

from collections.abc import Iterator
from urllib.parse import quote

import httpx


class StorageServiceClient:
    """Call storage-service using the private service token."""

    def __init__(self, *, base_url: str, token: str, timeout: float) -> None:
        """Create a client for storage-service HTTP APIs."""
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout

    def ensure_bucket(self, bucket: str) -> None:
        """Ensure the target bucket exists."""
        self._post_json("/buckets/ensure", {"bucket": bucket})

    def presign_put(
        self,
        *,
        bucket: str,
        object_key: str,
        content_type: str,
        expires_in: int,
    ) -> str:
        """Create a browser-usable PUT presigned URL."""
        payload = {
            "bucket": bucket,
            "object_key": object_key,
            "content_type": content_type,
            "expires_in": expires_in,
        }
        data = self._post_json("/presign/put", payload)
        return str(data["url"])

    def presign_get(self, *, bucket: str, object_key: str, expires_in: int) -> str:
        """Create a browser-usable GET presigned URL."""
        payload = {
            "bucket": bucket,
            "object_key": object_key,
            "expires_in": expires_in,
        }
        data = self._post_json("/presign/get", payload)
        return str(data["url"])

    def stat_object(self, *, bucket: str, object_key: str) -> dict:
        """Read object metadata from storage-service."""
        return self._post_json(
            "/objects/stat",
            {"bucket": bucket, "object_key": object_key},
        )

    def delete_object(self, *, bucket: str, object_key: str) -> None:
        """Delete an object from storage-service."""
        self._post_json("/objects/delete",
                        {"bucket": bucket, "object_key": object_key})

    def get_object_stream(self, *, bucket: str, object_key: str) -> Iterator[bytes]:
        """Stream object bytes through storage-service using internal auth."""
        url = self._object_url(bucket, object_key)
        with httpx.Client(timeout=self._timeout) as client:
            with client.stream("GET", url, headers=self._headers()) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes():
                    if chunk:
                        yield chunk

    def _post_json(self, path: str, payload: dict) -> dict:
        """POST JSON to storage-service and return ApiEnvelope data."""
        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(
                f"{self._base_url}{path}",
                json=payload,
                headers=self._headers(),
            )
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict) or "data" not in body:
                raise ValueError(
                    "storage-service response is not an ApiEnvelope")
            data = body["data"]
            if data is None:
                return {}
            if not isinstance(data, dict):
                raise ValueError(
                    "storage-service ApiEnvelope data must be an object")
            return data

    def _object_url(self, bucket: str, object_key: str) -> str:
        """Build the storage-service object path URL."""
        safe_bucket = quote(bucket, safe="")
        safe_key = quote(object_key, safe="/")
        return f"{self._base_url}/objects/{safe_bucket}/{safe_key}"

    def _headers(self) -> dict[str, str]:
        """Return storage-service auth headers."""
        return {"X-Storage-Service-Token": self._token}
