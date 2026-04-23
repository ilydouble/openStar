"""Session-scoped document attachment store.

Strategy (Plan 3):
  - Small docs (≤ INLINE_PER_DOC chars) → stored as full text in Redis, injected
    directly into the LLM system prompt every turn.
  - Large docs or when total inline budget is exceeded → stored in ChromaDB with
    tenant_code = session_id so knowledge_agent_tool can retrieve them.
  - When a new inline doc would exceed INLINE_TOTAL, the oldest inline doc(s) are
    automatically migrated to ChromaDB — invisible to the user.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
import structlog
import redis.asyncio as aioredis
from typing import Any

from ..config import settings

log = structlog.get_logger()

INLINE_PER_DOC = 40_000    # chars — docs larger than this go straight to RAG
INLINE_TOTAL   = 120_000   # chars — total inline budget across all session docs


def _inspect_data_file(
    path: Path, ext: str
) -> tuple[str, list[dict[str, str]], int | None, str]:
    """Extract a schema + head preview from a CSV / XLSX / XLS file.

    Returns (preview_md, columns, row_count, error). On failure the first
    three are best-effort empty values and error carries a human message.
    """
    try:
        import pandas as pd  # local import: dependency only required for data uploads
    except Exception as exc:
        return "", [], None, f"pandas unavailable: {exc}"

    n_rows = settings.data_preview_rows
    try:
        if ext == ".csv":
            df_head = pd.read_csv(path, nrows=n_rows)
            try:
                with path.open("rb") as fh:
                    row_count = max(sum(1 for _ in fh) - 1, 0)
            except Exception:
                row_count = None
        elif ext in (".xlsx", ".xls"):
            engine = "openpyxl" if ext == ".xlsx" else None
            df_head = pd.read_excel(path, nrows=n_rows, engine=engine)
            try:
                full = pd.read_excel(path, engine=engine, usecols=[0])
                row_count = int(len(full))
            except Exception:
                row_count = None
        else:
            return "", [], None, f"unsupported extension '{ext}'"
    except Exception as exc:
        return "", [], None, f"failed to parse: {exc}"

    columns = [
        {"name": str(c), "dtype": str(df_head[c].dtype)} for c in df_head.columns
    ]
    try:
        preview_md = df_head.to_markdown(index=False)
    except Exception:
        preview_md = df_head.to_string(index=False)
    return preview_md, columns, row_count, ""


class AttachmentStore:
    """Async Redis-backed per-session attachment list."""

    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None

    async def _get_client(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(
                settings.redis_url, encoding="utf-8", decode_responses=True
            )
        return self._redis

    def _key(self, session_id: str) -> str:
        return f"icore:attachments:{session_id}"

    async def _load(self, session_id: str) -> list[dict[str, Any]]:
        client = await self._get_client()
        raw = await client.get(self._key(session_id))
        if not raw:
            return []
        try:
            return json.loads(raw)
        except Exception:
            return []

    async def _save(self, session_id: str, data: list[dict[str, Any]]) -> None:
        client = await self._get_client()
        await client.set(
            self._key(session_id),
            json.dumps(data, ensure_ascii=False),
            ex=settings.memory_ttl_seconds,
        )

    # ── Migration helper ──────────────────────────────────────────────────────

    async def _migrate_to_rag(self, session_id: str, att: dict[str, Any]) -> None:
        """Move an inline attachment into ChromaDB (tenant scoped by session_id)."""
        from ..memory.chroma_store import add_documents
        from ..api.routers.knowledge import _chunk_text  # reuse existing chunker

        text = att.get("text", "")
        if not text:
            return
        chunks = _chunk_text(text, settings.rag_chunk_size, settings.rag_chunk_overlap)
        metadatas = [
            {"filename": att["filename"], "chunk_index": i, "source": att["filename"]}
            for i in range(len(chunks))
        ]
        add_documents(chunks=chunks, metadatas=metadatas, tenant_code=session_id)
        log.info("attachment_migrated_to_rag", session_id=session_id,
                 filename=att["filename"], chunks=len(chunks))

    # ── Public API ────────────────────────────────────────────────────────────

    async def add(self, session_id: str, filename: str, text: str) -> dict[str, Any]:
        """Add a document attachment. Returns the attachment info dict (without text)."""
        char_count = len(text)
        data = await self._load(session_id)

        # Replace same-named file if it already exists
        data = [a for a in data if a["filename"] != filename]

        if char_count > INLINE_PER_DOC:
            # Too large for inline — go straight to ChromaDB
            await self._migrate_to_rag(session_id, {"filename": filename, "text": text})
            att: dict[str, Any] = {
                "filename": filename, "char_count": char_count,
                "mode": "rag", "uploaded_at": time.time(),
            }
            data.append(att)
            await self._save(session_id, data)
            log.info("attachment_added_rag", session_id=session_id,
                     filename=filename, chars=char_count)
            return {k: v for k, v in att.items()}

        # Try inline — evict oldest inline docs until budget fits
        inline_docs = [a for a in data if a["mode"] == "inline"]
        current_inline = sum(a["char_count"] for a in inline_docs)

        while inline_docs and current_inline + char_count > INLINE_TOTAL:
            oldest = inline_docs.pop(0)
            await self._migrate_to_rag(session_id, oldest)
            current_inline -= oldest["char_count"]
            # Update mode in data list
            for a in data:
                if a["filename"] == oldest["filename"]:
                    a["mode"] = "rag"
                    a.pop("text", None)
                    break
            log.info("attachment_evicted_to_rag", session_id=session_id,
                     evicted=oldest["filename"])

        att = {
            "filename": filename, "char_count": char_count,
            "mode": "inline", "uploaded_at": time.time(), "text": text,
        }
        data.append(att)
        await self._save(session_id, data)
        log.info("attachment_added_inline", session_id=session_id,
                 filename=filename, chars=char_count)
        return {k: v for k, v in att.items() if k != "text"}

    async def list_info(self, session_id: str) -> list[dict[str, Any]]:
        """Return attachment list without the text field."""
        data = await self._load(session_id)
        return [{k: v for k, v in a.items() if k != "text"} for a in data]

    async def remove(self, session_id: str, filename: str) -> bool:
        """Remove an attachment. Returns True if found and removed."""
        data = await self._load(session_id)
        removed = [a for a in data if a["filename"] == filename]
        new_data = [a for a in data if a["filename"] != filename]
        if len(new_data) == len(data):
            return False
        # Also delete the backing file on disk for image / data attachments.
        for a in removed:
            if a.get("mode") == "image" and a.get("ref"):
                try:
                    (Path(settings.image_save_dir) / a["ref"]).unlink(missing_ok=True)
                except Exception as exc:
                    log.warning("image_file_unlink_failed", ref=a["ref"], error=str(exc))
            elif a.get("mode") == "data" and a.get("ref"):
                try:
                    (Path(settings.sequential_workspace).resolve() / a["ref"]).unlink(
                        missing_ok=True
                    )
                except Exception as exc:
                    log.warning("data_file_unlink_failed", ref=a["ref"], error=str(exc))
        await self._save(session_id, new_data)
        return True

    async def get_inline_text(self, session_id: str) -> str:
        """Return formatted inline document text for system prompt injection."""
        data = await self._load(session_id)
        inline = [a for a in data if a["mode"] == "inline" and a.get("text")]
        if not inline:
            return ""
        parts = []
        for a in inline:
            parts.append(f"### 文件：{a['filename']}\n\n{a['text']}")
        return "\n\n---\n\n".join(parts)

    async def has_rag_docs(self, session_id: str) -> bool:
        """Return True if any attachment is in RAG mode (needs knowledge_agent)."""
        data = await self._load(session_id)
        return any(a["mode"] == "rag" for a in data)

    async def add_image(
        self, session_id: str, filename: str, data: bytes
    ) -> dict[str, Any]:
        """Persist an uploaded image to disk and record its session reference."""
        session_dir = Path(settings.image_save_dir) / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        dest = session_dir / filename
        dest.write_bytes(data)

        ref = f"{session_id}/{filename}"
        record = {
            "filename": filename,
            "mode": "image",
            "ref": ref,
            "size": len(data),
            "uploaded_at": time.time(),
        }
        items = await self._load(session_id)
        items = [a for a in items if a["filename"] != filename]
        items.append(record)
        await self._save(session_id, items)
        log.info("attachment_added_image", session_id=session_id,
                 filename=filename, bytes=len(data))
        return record

    async def get_image_refs(self, session_id: str) -> list[dict[str, Any]]:
        """Return image attachments for injection into the orchestrator prompt."""
        data = await self._load(session_id)
        return [
            {"filename": a["filename"], "ref": a["ref"]}
            for a in data
            if a.get("mode") == "image" and a.get("ref")
        ]

    # ── Structured data files (CSV / Excel) ──────────────────────────────────

    async def add_data(
        self, session_id: str, filename: str, payload: bytes
    ) -> dict[str, Any]:
        """Persist a CSV / XLSX / XLS file to the agent workspace and record metadata.

        The file lands under ``{sequential_workspace}/data/{session_id}/{filename}``
        so code_executor's ``pd.read_csv("data/{session}/{filename}")`` works
        directly with its workspace cwd.
        """
        workspace_root = Path(settings.sequential_workspace).resolve()
        data_dir = workspace_root / "data" / session_id
        data_dir.mkdir(parents=True, exist_ok=True)
        dest = data_dir / filename
        dest.write_bytes(payload)

        rel_path = f"data/{session_id}/{filename}"
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        preview_md, columns_info, row_count, preview_error = _inspect_data_file(dest, ext)

        record: dict[str, Any] = {
            "filename": filename,
            "mode": "data",
            "ref": rel_path,
            "size": len(payload),
            "ext": ext,
            "row_count": row_count,         # may be None if unknown
            "columns": columns_info,        # list of {name, dtype}
            "preview_md": preview_md,       # markdown table of head(N)
            "preview_error": preview_error, # non-empty if parsing failed
            "uploaded_at": time.time(),
        }
        items = await self._load(session_id)
        items = [a for a in items if a["filename"] != filename]
        items.append(record)
        await self._save(session_id, items)
        log.info(
            "attachment_added_data", session_id=session_id, filename=filename,
            bytes=len(payload), rows=row_count, cols=len(columns_info or []),
        )
        return record

    async def get_data_refs(self, session_id: str) -> list[dict[str, Any]]:
        """Return data attachments for injection into the orchestrator prompt."""
        data = await self._load(session_id)
        workspace_root = Path(settings.sequential_workspace).resolve()
        return [
            {
                "filename": a["filename"],
                "ref": a["ref"],
                "abs_path": str(workspace_root / a["ref"]),
                "row_count": a.get("row_count"),
                "columns": a.get("columns") or [],
                "preview_md": a.get("preview_md") or "",
                "preview_error": a.get("preview_error") or "",
            }
            for a in data
            if a.get("mode") == "data" and a.get("ref")
        ]

    async def clear(self, session_id: str) -> None:
        client = await self._get_client()
        await client.delete(self._key(session_id))
        # Best-effort cleanup of image files on disk.
        try:
            session_dir = Path(settings.image_save_dir) / session_id
            if session_dir.exists():
                for f in session_dir.iterdir():
                    f.unlink(missing_ok=True)
                session_dir.rmdir()
        except Exception as exc:
            log.warning("image_dir_cleanup_failed", session_id=session_id, error=str(exc))
        # Best-effort cleanup of data files on disk.
        try:
            data_dir = Path(settings.sequential_workspace).resolve() / "data" / session_id
            if data_dir.exists():
                for f in data_dir.iterdir():
                    f.unlink(missing_ok=True)
                data_dir.rmdir()
        except Exception as exc:
            log.warning("data_dir_cleanup_failed", session_id=session_id, error=str(exc))


# App-level singleton
attachments = AttachmentStore()
