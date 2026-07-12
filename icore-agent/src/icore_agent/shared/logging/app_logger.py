"""Application-facing logger facade for backend module code."""

from __future__ import annotations

import sys
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from .contracts.v1 import LogLevel
from .logging_service_client import LoggingServiceClient, default_logging_client
from .sanitizer import sanitize_for_logging_service

_DEFAULT_SERVICE = "icore-backend"


class AppLogger:
    """Application-facing logger facade for module code."""

    def __init__(
        self,
        name: str,
        *,
        client: LoggingServiceClient | None = None,
        now: Callable[[], datetime] | None = None,
        service: str = _DEFAULT_SERVICE,
        bound_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Create a backend logger for one module or component."""
        self.name = name
        self._client = client or default_logging_client
        self._now = now or (lambda: datetime.now(UTC))
        self._service = service
        self._bound_metadata = bound_metadata or {}

    def bind(self, **metadata: Any) -> AppLogger:
        """Return a logger with additional metadata included in every event."""
        return AppLogger(
            self.name,
            client=self._client,
            now=self._now,
            service=self._service,
            bound_metadata={**self._bound_metadata, **metadata},
        )

    def debug(
        self, message: str, *, trace_id: str | None = None, **metadata: Any
    ) -> bool:
        """Emit a DEBUG event when backend debug logging is enabled."""
        if not self._debug_enabled():
            return False
        return self._emit(LogLevel.DEBUG, message, trace_id, metadata)

    def info(
        self, message: str, *, trace_id: str | None = None, **metadata: Any
    ) -> bool:
        """Emit an INFO event."""
        return self._emit(LogLevel.INFO, message, trace_id, metadata)

    def warning(
        self, message: str, *, trace_id: str | None = None, **metadata: Any
    ) -> bool:
        """Emit a WARNING event."""
        return self._emit(LogLevel.WARNING, message, trace_id, metadata)

    def error(
        self, message: str, *, trace_id: str | None = None, **metadata: Any
    ) -> bool:
        """Emit an ERROR event."""
        return self._emit(LogLevel.ERROR, message, trace_id, metadata)

    def exception(
        self, message: str, *, trace_id: str | None = None, **metadata: Any
    ) -> bool:
        """Emit an ERROR event with details from the active exception."""
        exc_type, exc_value, exc_traceback = sys.exc_info()
        if exc_type is not None and exc_value is not None:
            metadata.setdefault("error_type", exc_type.__name__)
            metadata.setdefault("error", str(exc_value))
            metadata.setdefault(
                "traceback",
                "".join(traceback.format_exception(
                    exc_type, exc_value, exc_traceback)),
            )
        return self._emit(LogLevel.ERROR, message, trace_id, metadata)

    def _emit(
        self,
        level: LogLevel,
        message: str,
        trace_id: str | None,
        metadata: dict[str, Any],
    ) -> bool:
        """Build and enqueue one logging-service event."""
        event_metadata = {
            "logger": self.name,
            **self._bound_metadata,
            **metadata,
        }
        sanitized = sanitize_for_logging_service(event_metadata)
        if not isinstance(sanitized, dict):
            sanitized = {"logger": self.name, "value": sanitized}
        try:
            return self._client.emit_event(
                level,
                message=message,
                service=self._service,
                trace_id=trace_id,
                metadata=sanitized,
                timestamp=self._now(),
            )
        except Exception as exc:  # noqa: BLE001 - logging must not break callers.
            print(
                f"[logging-service-fallback] backend logger emit failed: {exc}",
                file=sys.stderr,
            )
            return False

    @staticmethod
    def _debug_enabled() -> bool:
        """Return the runtime debug flag without creating config import cycles."""
        try:
            from icore_agent.config import settings

            return bool(settings.debug)
        except Exception:
            return False


def get_logger(
    name: str,
    *,
    client: LoggingServiceClient | None = None,
    now: Callable[[], datetime] | None = None,
    service: str = _DEFAULT_SERVICE,
) -> AppLogger:
    """Return a module-scoped backend logger that writes to logging-service."""
    return AppLogger(name, client=client, now=now, service=service)
