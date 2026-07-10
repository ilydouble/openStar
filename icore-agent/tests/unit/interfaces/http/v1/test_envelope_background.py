"""Tests for ApiEnvelope response metadata preservation."""

import json
from unittest.mock import MagicMock

from starlette.background import BackgroundTask
from starlette.responses import JSONResponse

from icore_agent.interfaces.http.v1.envelope import _wrap_success_response


def test_wrap_success_response_preserves_background_tasks() -> None:
    """ApiEnvelope wrapping must not drop Starlette background tasks."""
    request = MagicMock()
    request.url.path = "/api/v1/agent/session/demo/finalize"
    ran = {"value": False}

    def mark_ran() -> None:
        ran["value"] = True

    original = JSONResponse({"finalized": True, "session_id": "demo"})
    original.background = BackgroundTask(mark_ran)

    wrapped = _wrap_success_response(request, original)
    payload = json.loads(wrapped.body.decode("utf-8"))

    assert payload["data"]["finalized"] is True
    assert wrapped.background is original.background
    assert isinstance(wrapped.background, BackgroundTask)
