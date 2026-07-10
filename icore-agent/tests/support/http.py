"""HTTP helpers shared by in-process ASGI integration tests."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx


class ASGISyncTestClient:
    """Small synchronous wrapper around HTTPX ASGITransport."""

    def __init__(self, asgi_app: Any) -> None:
        """Create a test client bound to one ASGI application."""
        self._app = asgi_app

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Issue a GET request against the in-process application."""
        return self._request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        """Issue a POST request against the in-process application."""
        return self._request("POST", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        """Issue a DELETE request against the in-process application."""
        return self._request("DELETE", url, **kwargs)

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Run one ASGI request without Starlette's thread portal."""
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(
                self._async_request(method, url, **kwargs),
            )
        finally:
            asyncio.set_event_loop(None)
            loop.close()

    async def _async_request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute one request through HTTPX's asynchronous ASGI transport."""
        transport = httpx.ASGITransport(app=self._app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            request = asyncio.create_task(
                client.request(method, url, **kwargs))
            loop = asyncio.get_running_loop()
            start = loop.time()
            while True:
                if loop.time() - start > 30:
                    request.cancel()
                    raise TimeoutError(f"{method} {url} exceeded test timeout")
                try:
                    return await asyncio.wait_for(
                        asyncio.shield(request),
                        timeout=1.0,
                    )
                except TimeoutError:
                    continue


def api_data(response: httpx.Response) -> Any:
    """Return validated ApiEnvelope data from one test response."""
    payload = response.json()
    assert payload["code"] == response.status_code
    assert payload["message"]
    assert payload["timestamp"]
    return payload["data"]


def api_message(response: httpx.Response) -> str:
    """Return the validated ApiEnvelope message from one response."""
    payload = response.json()
    assert payload["code"] == response.status_code
    assert payload["timestamp"]
    return str(payload["message"])
