from __future__ import annotations

from datetime import UTC, datetime

from icore_agent.shared.http.request.request_context import clear_request_id, set_request_id
from icore_agent.shared.logging.app_logger import get_logger
from icore_agent.shared.logging.contracts.v1 import LogEvent, LogLevel
from icore_agent.shared.logging.logging_service_client import LoggingServiceClient


class CapturingLoggingClient(LoggingServiceClient):
    """Logger double that records events without starting the HTTP worker."""

    def __init__(self) -> None:
        """Create an in-memory logging-service client double."""
        super().__init__(
            base_url="http://logging-service:8091",
            token="token",
            timeout=1.0,
        )
        self.events: list[LogEvent] = []

    def _enqueue_event(self, event: LogEvent) -> bool:
        """Capture emitted events without sending them over HTTP."""
        self.events.append(event)
        return True


def _build_store(tmp_path, monkeypatch, *, debug: bool):
    """Build a store instance with deterministic code generation and captured logs."""
    import icore_agent.contexts.account.infrastructure.control_plane.json_store as store_module

    logging_client = CapturingLoggingClient()
    monkeypatch.setattr(
        store_module.settings,
        "control_plane_store_path",
        str(tmp_path / "control-plane.json"),
    )
    monkeypatch.setattr(store_module.settings, "debug", debug)
    monkeypatch.setattr(store_module.settings, "resend_api_key", "")
    monkeypatch.setattr(store_module.secrets, "randbelow", lambda _: 123456)
    monkeypatch.setattr(
        store_module, "_print_dev_verification_email", lambda *_: None)
    monkeypatch.setattr(
        store_module,
        "log",
        get_logger(
            "icore_agent.contexts.account.infrastructure.control_plane.json_store", client=logging_client),
    )

    return store_module.ControlPlaneStore(), logging_client


def test_send_verification_code_logs_debug_code_to_logging_service(tmp_path, monkeypatch):
    """Verify local development can read email codes from logging-service."""
    store, logging_client = _build_store(tmp_path, monkeypatch, debug=True)
    token = set_request_id("req-debug-code")
    try:
        success, _ = store.send_verification_code(
            "trial@example.com", "127.0.0.1")
    finally:
        clear_request_id(token)

    assert success is True
    assert len(logging_client.events) == 1
    event = logging_client.events[0]
    assert event.level == LogLevel.INFO
    assert event.service == "icore-backend"
    assert event.message == "verification_code_issued"
    assert event.trace_id == "req-debug-code"
    assert event.metadata["email"] == "trial@example.com"
    assert event.metadata["client_ip"] == "127.0.0.1"
    assert event.metadata["verification_code"] == "123456"


def test_send_verification_code_omits_code_outside_debug(tmp_path, monkeypatch):
    """Verify production logs do not leak one-time verification codes."""
    store, logging_client = _build_store(tmp_path, monkeypatch, debug=False)
    store.send_verification_code("trial@example.com", "127.0.0.1")

    assert len(logging_client.events) == 1
    event = logging_client.events[0]
    assert event.service == "icore-backend"
    assert event.timestamp.tzinfo is not None
    assert event.timestamp <= datetime.now(UTC)
    assert "verification_code" not in event.metadata
