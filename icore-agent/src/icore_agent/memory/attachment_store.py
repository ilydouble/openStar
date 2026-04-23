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
import structlog
import redis.asyncio as aioredis
from typing import Any

from ..config import settings

log = structlog.get_logger()

INLINE_PER_DOC = 40_000    # chars — docs larger than this go straight to RAG
INLINE_TOTAL   = 120_000   # chars — total inline budget across all session docs


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
        new_data = [a for a in data if a["filename"] != filename]
        if len(new_data) == len(data):
            return False
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

    async def clear(self, session_id: str) -> None:
        client = await self._get_client()
        await client.delete(self._key(session_id))


# App-level singleton
attachments = AttachmentStore()
