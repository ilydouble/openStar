"""Catalog of structured tools available to agent runners."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from icore_agent.domain.agent.tool import (
    ToolDefinition,
    ToolExecutionContext,
    ToolExecutor,
)

from .chroma_search import chroma_search as _chroma_search
from .code_executor import run_python_snippet
from .email_tools import list_inbox, search_emails, send_email
from .fetch_webpage import fetch_webpage
from .file_ops import list_files, read_file, write_file
from .http_client import http_request
from .image_tools import generate_image as _generate_image
from .image_tools import understand_image
from .number_comparator import number_comparator
from .uploaded_files import read_uploaded_file
from .web_search import web_search


def build_orchestrator_tool_definitions(
    *,
    session_id: str,
    user_id: str = "",
    file_service: Any | None = None,
) -> list[ToolDefinition]:
    """Return structured tool definitions mounted on the main agent."""
    return [
        _definition(
            name="number_comparator",
            label="Number comparator",
            description=(
                "Compare two numeric values deterministically, with optional "
                "absolute tolerance for near-equality."
            ),
            parameters=_NUMBER_COMPARATOR_SCHEMA,
            execute=_callable_executor(number_comparator),
            prompt_snippet=(
                "Compare close numeric values deterministically when precision matters."
            ),
        ),
        _definition(
            name="web_search",
            label="Web search",
            description=(
                "Search the public web for current information and return "
                "ranked snippets with URLs."
            ),
            parameters=_WEB_SEARCH_SCHEMA,
            execute=_callable_executor(web_search),
            prompt_snippet=(
                "Search the public web for current facts, sources, and news."
            ),
        ),
        _definition(
            name="fetch_webpage",
            label="Fetch webpage",
            description=(
                "Fetch a specific webpage and return readable text content."
            ),
            parameters=_FETCH_WEBPAGE_SCHEMA,
            execute=_callable_executor(fetch_webpage),
            prompt_snippet=(
                "Read the full text of a specific URL after choosing a source."
            ),
        ),
        _definition(
            name="http_request",
            label="HTTP request",
            description=(
                "Call an external HTTP API and return status, content type, "
                "and a truncated response body."
            ),
            parameters=_HTTP_REQUEST_SCHEMA,
            execute=_callable_executor(http_request),
            prompt_snippet=(
                "Call an HTTP API when the user asks for structured API access."
            ),
        ),
        _definition(
            name="run_python_snippet",
            label="Run Python snippet",
            description=(
                "Run a short Python snippet in the configured workspace for "
                "calculation or data inspection."
            ),
            parameters=_RUN_PYTHON_SNIPPET_SCHEMA,
            execute=_callable_executor(run_python_snippet),
            prompt_snippet=(
                "Run Python for calculations, data checks, or quick logic validation."
            ),
        ),
        _definition(
            name="list_files",
            label="List files",
            description="List files and directories inside the agent workspace.",
            parameters=_LIST_FILES_SCHEMA,
            execute=_callable_executor(list_files),
            prompt_snippet=(
                "Inspect workspace files before reading or writing project files."
            ),
        ),
        _definition(
            name="read_file",
            label="Read file",
            description="Read a text file from inside the agent workspace.",
            parameters=_READ_FILE_SCHEMA,
            execute=_callable_executor(read_file),
            prompt_snippet="Read workspace file contents by relative path.",
        ),
        _definition(
            name="write_file",
            label="Write file",
            description="Write text content to a file inside the agent workspace.",
            parameters=_WRITE_FILE_SCHEMA,
            execute=_callable_executor(write_file),
            prompt_snippet="Write or update workspace files by relative path.",
        ),
        _definition(
            name="read_uploaded_file",
            label="Read uploaded file",
            description=(
                "Read a user-uploaded non-image file by attachment UUID and "
                "return model-readable text."
            ),
            parameters=_READ_UPLOADED_FILE_SCHEMA,
            execute=_scoped_uploaded_file_executor(
                user_id=user_id,
                file_service=file_service,
            ),
            prompt_snippet=(
                "Read an uploaded file_attachment by UUID when the user asks "
                "about its contents."
            ),
        ),
        _definition(
            name="chroma_search",
            label="Knowledge search",
            description=(
                "Search uploaded or internal knowledge documents scoped to "
                "the current session."
            ),
            parameters=_CHROMA_SEARCH_SCHEMA,
            execute=_scoped_chroma_executor(session_id),
            prompt_snippet=(
                "Search session-scoped internal knowledge documents before using the web."
            ),
        ),
        _definition(
            name="understand_image",
            label="Understand image",
            description="Analyze an image and answer a question about it.",
            parameters=_UNDERSTAND_IMAGE_SCHEMA,
            execute=_callable_executor(understand_image),
            prompt_snippet="Analyze an existing image from a URL or session path.",
        ),
        _definition(
            name="generate_image",
            label="Generate image",
            description=(
                "Generate an image from a text prompt and store the result "
                "for the current session when possible."
            ),
            parameters=_GENERATE_IMAGE_SCHEMA,
            execute=_scoped_generate_image_executor(session_id),
            prompt_snippet="Generate a new image from a detailed text prompt.",
        ),
    ]


def chroma_search(query: str, tenant_code: str = "", top_k: int = 5) -> str:
    """Search internal knowledge documents with an explicit tenant scope."""
    return _chroma_search(query=query, tenant_code=tenant_code, top_k=top_k)


def generate_image(prompt: str, size: str = "1024x1024", session_id: str = "") -> str:
    """Generate an image with an explicit session scope."""
    return _generate_image(prompt=prompt, size=size, session_id=session_id)


def _definition(
    *,
    name: str,
    label: str,
    description: str,
    parameters: dict[str, Any],
    execute: ToolExecutor,
    prompt_snippet: str,
) -> ToolDefinition:
    """Create one structured tool definition from catalog metadata."""
    return ToolDefinition(
        name=name,
        label=label,
        description=description,
        parameters=parameters,
        execute=execute,
        prompt_snippet=prompt_snippet,
    )


def _callable_executor(func: Callable[..., Any]) -> ToolExecutor:
    """Wrap an existing callable tool implementation as a ToolExecutor."""

    def _execute(
        _tool_call_id: str,
        params: dict[str, Any],
        _context: ToolExecutionContext,
    ) -> Any:
        """Call the wrapped tool with prepared keyword arguments."""
        return func(**params)

    return _execute


def _scoped_chroma_executor(session_id: str) -> ToolExecutor:
    """Bind the current session as the Chroma tenant scope."""

    def _execute(
        _tool_call_id: str,
        params: dict[str, Any],
        _context: ToolExecutionContext,
    ) -> str:
        """Run Chroma search with the session tenant injected."""
        return _chroma_search(
            query=str(params.get("query") or ""),
            tenant_code=session_id,
            top_k=int(params.get("top_k") or 5),
        )

    return _execute


def _scoped_generate_image_executor(session_id: str) -> ToolExecutor:
    """Bind the current session to generated image storage."""

    def _execute(
        _tool_call_id: str,
        params: dict[str, Any],
        _context: ToolExecutionContext,
    ) -> str:
        """Generate an image with the session id injected."""
        return _generate_image(
            prompt=str(params.get("prompt") or ""),
            size=str(params.get("size") or "1024x1024"),
            session_id=session_id,
        )

    return _execute


def _scoped_uploaded_file_executor(
    *,
    user_id: str,
    file_service: Any | None,
) -> ToolExecutor:
    """Bind uploaded-file reads to the current authenticated user."""

    def _execute(
        _tool_call_id: str,
        params: dict[str, Any],
        _context: ToolExecutionContext,
    ) -> str:
        """Read one uploaded file by UUID from the current user's assets."""
        return read_uploaded_file(
            file_service=file_service,
            user_id=user_id,
            file_uuid=str(params.get("file_uuid") or ""),
            encoding=str(params.get("encoding") or "utf-8"),
        )

    return _execute


_NUMBER_COMPARATOR_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "left": {"type": "number", "description": "First numeric value."},
        "right": {"type": "number", "description": "Second numeric value."},
        "tolerance": {
            "type": "number",
            "default": 0.0,
            "description": "Absolute tolerance for treating values as equal.",
        },
    },
    "required": ["left", "right"],
    "additionalProperties": False,
}

_WEB_SEARCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Search query."},
        "max_results": {
            "type": "integer",
            "default": 5,
            "minimum": 1,
            "maximum": 10,
        },
    },
    "required": ["query"],
    "additionalProperties": False,
}

_FETCH_WEBPAGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "url": {"type": "string", "description": "Absolute URL to fetch."},
    },
    "required": ["url"],
    "additionalProperties": False,
}

_HTTP_REQUEST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "url": {"type": "string"},
        "method": {
            "type": "string",
            "default": "GET",
            "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
        },
        "headers": {
            "type": "object",
            "additionalProperties": {"type": "string"},
        },
        "body": {
            "anyOf": [
                {"type": "object"},
                {"type": "string"},
                {"type": "null"},
            ],
        },
    },
    "required": ["url"],
    "additionalProperties": False,
}

_RUN_PYTHON_SNIPPET_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "code": {"type": "string"},
        "timeout": {
            "type": "integer",
            "default": 30,
            "minimum": 5,
            "maximum": 120,
        },
    },
    "required": ["code"],
    "additionalProperties": False,
}

_LIST_FILES_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "directory": {"type": "string", "default": "."},
        "max_depth": {
            "type": "integer",
            "default": 2,
            "minimum": 1,
            "maximum": 8,
        },
    },
    "additionalProperties": False,
}

_READ_FILE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {"type": "string"},
        "encoding": {"type": "string", "default": "utf-8"},
    },
    "required": ["path"],
    "additionalProperties": False,
}

_WRITE_FILE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {"type": "string"},
        "content": {"type": "string"},
        "encoding": {"type": "string", "default": "utf-8"},
    },
    "required": ["path", "content"],
    "additionalProperties": False,
}

_READ_UPLOADED_FILE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "file_uuid": {
            "type": "string",
            "description": "UUID from the file_attachment metadata.",
        },
        "encoding": {"type": "string", "default": "utf-8"},
    },
    "required": ["file_uuid"],
    "additionalProperties": False,
}

_CHROMA_SEARCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "top_k": {
            "type": "integer",
            "default": 5,
            "minimum": 1,
            "maximum": 20,
        },
    },
    "required": ["query"],
    "additionalProperties": False,
}

_UNDERSTAND_IMAGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "image_source": {
            "type": "string",
            "description": "URL, data URI, or session-local image path.",
        },
        "question": {"type": "string", "default": ""},
    },
    "required": ["image_source"],
    "additionalProperties": False,
}

_GENERATE_IMAGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "prompt": {"type": "string"},
        "size": {
            "type": "string",
            "default": "1024x1024",
            "enum": [
                "1024x1024",
                "768x1344",
                "864x1152",
                "1344x768",
                "1152x864",
                "1440x720",
                "720x1440",
            ],
        },
    },
    "required": ["prompt"],
    "additionalProperties": False,
}


__all__ = [
    "build_orchestrator_tool_definitions",
    "chroma_search",
    "fetch_webpage",
    "generate_image",
    "http_request",
    "list_files",
    "list_inbox",
    "number_comparator",
    "read_file",
    "read_uploaded_file",
    "run_python_snippet",
    "search_emails",
    "send_email",
    "understand_image",
    "web_search",
    "write_file",
]
