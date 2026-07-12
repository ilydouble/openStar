"""Internal client that queues and delivers events to logging-service."""

from __future__ import annotations

import asyncio
import queue
import sys
import threading
import time
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import httpx

from icore_agent.config import settings
from icore_agent.shared.http.request.request_context import get_request_id
from icore_agent.shared.logging.contracts.v1 import (
    LogEvent,
    LogEventIngestRequest,
    LogLevel,
    model_to_json_dict,
)


class LoggingServiceClient:
    """Queue and deliver LogEvent objects to the Go logging-service."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float | None = None,
        sync_transport: httpx.BaseTransport | None = None,
        queue_size: int = 4096,
    ) -> None:
        """Configure the logging-service endpoint and local non-blocking queue."""
        self.base_url = (base_url or settings.logging_service_url).rstrip("/")
        self.logging_service_token = (
            token if token is not None else settings.logging_service_token
        )
        self.timeout = timeout if timeout is not None else settings.logging_service_timeout
        self.sync_transport = sync_transport
        self._queue: queue.Queue[LogEvent] = queue.Queue(maxsize=queue_size)
        self._worker_started = False
        self._worker: threading.Thread | None = None
        self._state_lock = threading.Lock()
        self._stop_requested = threading.Event()
        self._worker_done = threading.Event()
        self._closed = False
        self._last_fallback_warning = 0.0
        self._client: httpx.Client | None = None

    def emit_event(
        self,
        level: LogLevel,
        *,
        message: str,
        service: str,
        trace_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> bool:
        """Build and enqueue a LogEvent without waiting for the HTTP delivery worker."""
        if not isinstance(cast(object, level), LogLevel):
            raise TypeError("level must be a LogLevel")

        resolved_trace_id = trace_id if trace_id is not None else get_request_id() or ""
        event = LogEvent(
            event_id=str(uuid4()),
            timestamp=timestamp or datetime.now(UTC),
            level=level,
            service=service,
            message=message,
            trace_id=resolved_trace_id,
            metadata=metadata or {},
        )
        return self._enqueue_event(event)

    def _enqueue_event(self, event: LogEvent) -> bool:
        """Put an event on the worker queue and drop it explicitly if the queue is full."""
        with self._state_lock:
            if self._closed:
                self._fallback_warning(
                    "logging-service client is closed; dropping log event"
                )
                return False
            self._ensure_worker_locked()
            try:
                self._queue.put_nowait(event)
                return True
            except queue.Full:
                self._fallback_warning(
                    "logging-service queue is full; dropping log event")
                return False

    def _send_event_sync(self, event: LogEvent) -> bool:
        """Send a single queued event to logging-service using the JSON HTTP contract."""
        request = LogEventIngestRequest(event=event)
        headers = {"X-Logging-Service-Token": self.logging_service_token}
        if event.trace_id:
            headers["X-Request-ID"] = event.trace_id

        try:
            response = self._get_client().post(
                f"{self.base_url}/v1/log-events",
                json=model_to_json_dict(request),
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json() if response.content else {}
        except Exception as exc:  # noqa: BLE001 - logging must never block business flow.
            self._fallback_warning(f"logging-service emit failed: {exc}")
            return False

        if isinstance(payload, dict) and payload.get("code", 200) >= 400:
            self._fallback_warning(
                f"logging-service rejected event: {payload}")
            return False
        return True

    def close(self, *, timeout: float | None = None) -> bool:
        """Stop accepting events and wait for the delivery worker to drain its queue."""
        drain_timeout = self._drain_timeout(timeout)
        if self._request_close() is None:
            return True

        if self._worker_done.wait(timeout=drain_timeout):
            return True

        self._warn_drain_timeout()
        return False

    async def aclose(self, *, timeout: float | None = None) -> bool:
        """Drain and close the logging client without blocking the asyncio event loop."""
        drain_timeout = self._drain_timeout(timeout)
        if self._request_close() is None:
            return True

        loop = asyncio.get_running_loop()
        deadline = loop.time() + drain_timeout
        while not self._worker_done.is_set():
            remaining = deadline - loop.time()
            if remaining <= 0:
                self._warn_drain_timeout()
                return False
            await asyncio.sleep(min(0.05, remaining))
        return True

    @staticmethod
    def _drain_timeout(timeout: float | None) -> float:
        """Resolve an explicit or configured non-negative drain timeout."""
        configured = settings.logging_client_drain_timeout if timeout is None else timeout
        return max(configured, 0.0)

    def _request_close(self) -> threading.Thread | None:
        """Atomically close the enqueue side and request worker termination."""
        with self._state_lock:
            self._closed = True
            self._stop_requested.set()
            worker = self._worker

        if worker is None:
            self._close_http_client()
            self._worker_done.set()
        return worker

    def _warn_drain_timeout(self) -> None:
        """Report how many queued events remain after a bounded drain wait."""
        self._fallback_warning(
            "logging-service drain timed out; "
            f"remaining_events={self._queue.qsize()}"
        )

    def _close_http_client(self) -> None:
        """Close the reusable HTTP client after its worker no longer uses it."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def _get_client(self) -> httpx.Client:
        """Return the reusable sync HTTP client for the logging worker."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                timeout=self.timeout, transport=self.sync_transport)
        return self._client

    def _ensure_worker_locked(self) -> None:
        """Start the daemon worker while the client state lock is held."""
        if self._worker_started:
            return
        self._worker_started = True
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    def _worker_loop(self) -> None:
        """Continuously send queued events while isolating failures from application code."""
        try:
            while True:
                if self._stop_requested.is_set() and self._queue.empty():
                    return
                try:
                    event = self._queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                try:
                    self._send_event_sync(event)
                finally:
                    self._queue.task_done()
        finally:
            self._close_http_client()
            self._worker_done.set()

    def _fallback_warning(self, message: str) -> None:
        """Print throttled local fallback warnings when logging-service delivery fails."""
        now = time.monotonic()
        if now - self._last_fallback_warning < 30:
            return
        self._last_fallback_warning = now
        print(f"[logging-service-fallback] {message}", file=sys.stderr)


default_logging_client = LoggingServiceClient()
