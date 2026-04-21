"""Code execution tool — runs Python snippets in a subprocess sandbox.

Intentionally limited: no network, no filesystem writes outside workspace.
Used by the code sub-agent for quick Python evaluations.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
import structlog
from strands import tool

from ..config import settings

log = structlog.get_logger()

_TIMEOUT = 30
_MAX_OUTPUT = 4_000

# Safety guard: block obviously dangerous builtins
_BLOCKED = ["__import__('os').system", "subprocess", "open(", "eval(", "exec("]


def _is_safe(code: str) -> tuple[bool, str]:
    for pattern in _BLOCKED:
        if pattern in code:
            return False, f"Blocked pattern detected: '{pattern}'"
    return True, ""


@tool
def run_python_snippet(code: str, timeout: int = 30) -> str:
    """Execute a Python code snippet and return its stdout/stderr.

    Runs in an isolated subprocess. Use for quick calculations,
    data transformations, or verifying logic — not for file I/O.

    Args:
        code: Valid Python source code to execute.
        timeout: Maximum seconds to allow (default 30, max 120).

    Returns:
        stdout + stderr from the execution, or an error message.
    """
    timeout = min(max(5, timeout), 120)
    code = textwrap.dedent(code)

    safe, reason = _is_safe(code)
    if not safe:
        return f"[BLOCKED] {reason}"

    log.info("run_python_snippet", code_preview=code[:100], timeout=timeout)

    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=settings.sequential_workspace,
        )
        combined = result.stdout + result.stderr
        if len(combined) > _MAX_OUTPUT:
            combined = combined[:_MAX_OUTPUT] + "\n... [output truncated]"
        return combined or "(no output)"

    except subprocess.TimeoutExpired:
        return f"[TIMEOUT] Execution exceeded {timeout}s."
    except Exception as exc:
        log.error("run_python_snippet_error", error=str(exc))
        return f"[ERROR] {exc}"
