"""Shared ApiEnvelope support for HTTP v1 JSON responses."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any, Generic, TypeVar

from fastapi import FastAPI, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse, Response

T = TypeVar("T")

_ENVELOPE_KEYS = {"code", "message", "data", "timestamp"}
_HEADER_SKIP = {"content-length", "content-type"}
_JSON_MEDIA_TYPE = "application/json"
_INSTALL_STATE_KEY = "_icore_api_envelope_installed"


class ApiEnvelope(BaseModel, Generic[T]):
    """Describe the stable HTTP v1 JSON response contract."""

    code: int
    message: str
    data: T | None
    timestamp: str
    error_code: str | None = None


def make_api_envelope(
    *,
    code: int,
    message: str,
    data: Any,
    error_code: str | None = None,
) -> dict[str, Any]:
    """Build the JSON-ready ApiEnvelope payload used by HTTP v1."""
    envelope: dict[str, Any] = {
        "code": code,
        "message": message,
        "data": data,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if error_code:
        envelope["error_code"] = error_code
    return envelope


def is_api_envelope(payload: Any) -> bool:
    """Return whether a JSON payload already matches the ApiEnvelope shape."""
    return isinstance(payload, dict) and _ENVELOPE_KEYS.issubset(payload.keys())


def install_api_envelope(app: FastAPI) -> None:
    """Install ApiEnvelope exception handlers once on a FastAPI application."""
    if getattr(app.state, _INSTALL_STATE_KEY, False):
        return
    app.add_exception_handler(
        StarletteHTTPException,
        api_http_exception_handler,
    )
    app.add_exception_handler(
        RequestValidationError,
        api_validation_exception_handler,
    )
    setattr(app.state, _INSTALL_STATE_KEY, True)


class ApiEnvelopeRoute(APIRoute):
    """Wrap successful JSON route responses in ApiEnvelope."""

    def get_route_handler(self):
        """Return the route handler with ApiEnvelope normalization applied."""
        original_route_handler = super().get_route_handler()

        async def route_handler(request: Request) -> Response:
            """Run the original handler and wrap JSON responses."""
            response = await original_route_handler(request)
            return _wrap_success_response(request, response)

        return route_handler


async def api_http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> Response:
    """Return ApiEnvelope errors for v1 HTTP exceptions."""
    if not _path_is_wrapped(request.url.path):
        return await http_exception_handler(request, exc)
    return JSONResponse(
        make_api_envelope(
            code=exc.status_code,
            message=str(exc.detail),
            data=None,
            error_code=_error_code(exc.status_code),
        ),
        status_code=exc.status_code,
        headers=exc.headers,
    )


async def api_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> Response:
    """Return ApiEnvelope errors for v1 request validation failures."""
    if not _path_is_wrapped(request.url.path):
        return await request_validation_exception_handler(request, exc)
    return JSONResponse(
        make_api_envelope(
            code=422,
            message=json.dumps(exc.errors(), ensure_ascii=False),
            data=None,
            error_code=_error_code(422),
        ),
        status_code=422,
    )


def _should_wrap(response: Response) -> bool:
    """Return whether this response should be normalized to ApiEnvelope."""
    if response.status_code in {204, 304}:
        return False
    content_type = response.headers.get("content-type", "")
    return _JSON_MEDIA_TYPE in content_type.lower()


def _path_is_wrapped(path: str) -> bool:
    """Return whether a route belongs to the HTTP v1 JSON contract surface."""
    return path in {"/health", "/ready"} or path.startswith("/api/v1/")


def _wrap_success_response(request: Request, response: Response) -> Response:
    """Wrap one successful route response when it belongs to the v1 JSON surface."""
    if not _path_is_wrapped(request.url.path) or not _should_wrap(response):
        return response
    body = getattr(response, "body", b"")
    try:
        payload = json.loads(body.decode("utf-8")) if body else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        return response
    envelope = _envelope_for_payload(response.status_code, payload)
    if envelope is payload:
        return response
    return JSONResponse(
        envelope,
        status_code=response.status_code,
        headers=_copy_headers(response),
    )


def _envelope_for_payload(status_code: int, payload: Any) -> dict[str, Any]:
    """Build an ApiEnvelope for one response payload."""
    if is_api_envelope(payload):
        return payload
    if status_code >= 400:
        return make_api_envelope(
            code=status_code,
            message=_error_message(payload),
            data=None,
            error_code=_error_code(status_code),
        )
    return make_api_envelope(
        code=status_code,
        message="操作成功",
        data=payload,
    )


def _copy_headers(response: Response) -> dict[str, str]:
    """Copy response headers that should survive a JSON body rewrite."""
    return {
        key: value
        for key, value in response.headers.items()
        if key.lower() not in _HEADER_SKIP
    }


def _error_message(payload: Any) -> str:
    """Extract the most useful error message from a FastAPI error payload."""
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if detail:
            return detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)
        message = payload.get("message")
        if message:
            return str(message)
    return "请求失败"


def _error_code(status_code: int) -> str:
    """Return the standard HTTP reason phrase for an error status."""
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "HTTPError"
