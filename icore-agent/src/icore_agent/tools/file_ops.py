"""File operation tools — read and write files within the agent workspace.

All paths are sandboxed to settings.sequential_workspace.
"""

from __future__ import annotations

import os
import structlog
from pathlib import Path
from strands import tool

from ..config import settings

log = structlog.get_logger()

_MAX_READ_BYTES = settings.file_ops_max_size_mb * 1024 * 1024


def _safe_path(relative_path: str) -> Path:
    """Resolve path and ensure it stays inside the workspace."""
    workspace = Path(settings.sequential_workspace).resolve()
    target = (workspace / relative_path).resolve()
    if not str(target).startswith(str(workspace)):
        raise PermissionError(f"Path escape attempt: {relative_path!r}")
    return target


@tool
def read_file(path: str, encoding: str = "utf-8") -> str:
    """Read a file from the agent workspace.

    Args:
        path: Relative path inside the workspace directory.
        encoding: File encoding (default utf-8).

    Returns:
        File contents as a string, or an error message.
    """
    log.info("read_file", path=path)
    try:
        target = _safe_path(path)
        if not target.exists():
            return f"[NOT FOUND] {path}"
        size = target.stat().st_size
        if size > _MAX_READ_BYTES:
            return f"[TOO LARGE] File is {size / 1e6:.1f} MB; limit is {settings.file_ops_max_size_mb} MB."
        return target.read_text(encoding=encoding)
    except PermissionError as exc:
        return f"[PERMISSION DENIED] {exc}"
    except Exception as exc:
        log.error("read_file_error", error=str(exc))
        return f"[ERROR] {exc}"


@tool
def write_file(path: str, content: str, encoding: str = "utf-8") -> str:
    """Write content to a file in the agent workspace (creates directories as needed).

    Args:
        path: Relative path inside the workspace directory.
        content: Text content to write.
        encoding: File encoding (default utf-8).

    Returns:
        Success message or error.
    """
    log.info("write_file", path=path, size=len(content))
    try:
        target = _safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding=encoding)
        return f"Written {len(content)} chars to {path}"
    except PermissionError as exc:
        return f"[PERMISSION DENIED] {exc}"
    except Exception as exc:
        log.error("write_file_error", error=str(exc))
        return f"[ERROR] {exc}"


@tool
def list_files(directory: str = ".", max_depth: int = 2) -> str:
    """List files and directories inside the agent workspace.

    Use this to understand the project structure before reading or editing files.

    Args:
        directory: Relative path of the directory to list (default: workspace root).
        max_depth: How many levels deep to recurse (1 = top-level only, default 2).

    Returns:
        A tree-style text listing of files with sizes, or an error message.
    """
    log.info("list_files", directory=directory, max_depth=max_depth)
    try:
        root = _safe_path(directory)
        if not root.exists():
            return f"[NOT FOUND] {directory}"
        if not root.is_dir():
            return f"[NOT A DIRECTORY] {directory}"

        lines: list[str] = [f"{directory}/"]

        def _walk(path: Path, depth: int, prefix: str) -> None:
            if depth > max_depth:
                return
            try:
                entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
            except PermissionError:
                lines.append(f"{prefix}[permission denied]")
                return
            for i, entry in enumerate(entries):
                connector = "└── " if i == len(entries) - 1 else "├── "
                if entry.is_dir():
                    lines.append(f"{prefix}{connector}{entry.name}/")
                    extension = "    " if i == len(entries) - 1 else "│   "
                    _walk(entry, depth + 1, prefix + extension)
                else:
                    size = entry.stat().st_size
                    size_str = (
                        f"{size / 1024:.1f} KB" if size >= 1024 else f"{size} B"
                    )
                    lines.append(f"{prefix}{connector}{entry.name}  ({size_str})")

        _walk(root, 1, "")
        return "\n".join(lines)
    except PermissionError as exc:
        return f"[PERMISSION DENIED] {exc}"
    except Exception as exc:
        log.error("list_files_error", error=str(exc))
        return f"[ERROR] {exc}"
