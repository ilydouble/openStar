"""Application service for knowledge upload and retrieval orchestration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from icore_agent.contexts.account.domain.user import AuthenticatedUser

from .parsers import parse_file
from .text import chunk_text


class KnowledgeService:
    """Coordinate knowledge parsing, chunking, storage, and tenant resolution."""

    def __init__(
        self,
        *,
        add_documents: Callable[..., int],
        list_documents: Callable[..., list[dict[str, Any]]],
        get_collection: Callable[..., Any],
        rag_chunk_size: int,
        rag_chunk_overlap: int,
        file_size_limit_mb: int,
    ) -> None:
        """Bind the service to storage adapters and ingestion configuration."""
        self._add_documents = add_documents
        self._list_documents = list_documents
        self._get_collection = get_collection
        self._rag_chunk_size = rag_chunk_size
        self._rag_chunk_overlap = rag_chunk_overlap
        self._file_size_limit_mb = file_size_limit_mb

    def resolve_tenant_code(
        self,
        user: AuthenticatedUser,
        *,
        tenant_code: str,
        scope: str,
    ) -> str:
        """Resolve the tenant code from explicit input or the user/session scope."""
        if tenant_code.strip():
            return tenant_code.strip()
        if scope == "private":
            return user.public_id
        if scope == "organization":
            return f"org:{user.organization_id or ''}"
        return ""

    def parse_document(self, filename: str, data: bytes) -> str:
        """Parse one uploaded knowledge document into plain text."""
        return parse_file(filename, data)

    def ensure_file_size(self, data: bytes) -> None:
        """Reject documents that exceed the configured upload size budget."""
        max_bytes = self._file_size_limit_mb * 1024 * 1024
        if len(data) > max_bytes:
            raise ValueError(
                f"File exceeds {self._file_size_limit_mb} MB limit")

    def chunk_document(self, text: str) -> list[str]:
        """Chunk plain text according to the configured RAG settings."""
        return chunk_text(text, self._rag_chunk_size, self._rag_chunk_overlap)

    def store_document(
        self,
        *,
        filename: str,
        text: str,
        tenant_code: str,
    ) -> int:
        """Persist a parsed document into the knowledge store and return chunk count."""
        chunks = self.chunk_document(text)
        if not chunks:
            raise ValueError("File appears to be empty or unreadable")
        metadatas = [
            {"filename": filename, "chunk_index": i, "source": filename}
            for i in range(len(chunks))
        ]
        return self._add_documents(chunks=chunks, metadatas=metadatas, tenant_code=tenant_code)

    def list_documents(self, *, tenant_code: str) -> list[dict[str, Any]]:
        """Return the document list for one resolved tenant scope."""
        return self._list_documents(tenant_code=tenant_code)

    def delete_document(self, *, filename: str, tenant_code: str) -> int:
        """Delete all indexed chunks belonging to one uploaded document."""
        collection = self._get_collection(tenant_code=tenant_code)
        results = collection.get(
            where={"filename": filename}, include=["metadatas"])
        ids = results.get("ids") or []
        if not ids:
            raise LookupError(f"Document '{filename}' not found")
        collection.delete(ids=ids)
        return len(ids)
