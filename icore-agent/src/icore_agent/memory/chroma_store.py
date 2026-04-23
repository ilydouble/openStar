"""ChromaDB wrapper for document RAG.

Architecture:
  - One persistent ChromaDB client, one logical collection per tenant.
  - Collection name = f"{settings.chroma_collection}_{tenant_code}"
    (empty tenant_code → "icore_docs_shared").
  - Embedding: Zhipu embedding-3 via OpenAI-compatible SDK.
  - Each document chunk stored with metadata:
      {"filename": str, "chunk_index": int, "source": str}
"""

from __future__ import annotations

import hashlib
import structlog
from typing import Any

import chromadb
from chromadb import EmbeddingFunction, Embeddings
from openai import OpenAI

from ..config import settings

log = structlog.get_logger()


# ── Zhipu Embedding Function ─────────────────────────────────────────────────

class ZhipuEmbeddingFunction(EmbeddingFunction):
    """ChromaDB-compatible embedding function using Zhipu embedding-3."""

    def __init__(self) -> None:
        self._client = OpenAI(
            api_key=settings.zai_api_key,
            base_url=settings.zhipu_api_base,
        )
        self._model = settings.zhipu_embed_model

    def __call__(self, input: list[str]) -> Embeddings:  # noqa: A002
        # embedding-3 supports batch up to 64 items; chunk if needed
        results: list[list[float]] = []
        batch_size = 16
        for i in range(0, len(input), batch_size):
            batch = input[i : i + batch_size]
            resp = self._client.embeddings.create(model=self._model, input=batch)
            results.extend([item.embedding for item in resp.data])
        return results


# ── Singleton client + embedding fn ─────────────────────────────────────────

_chroma_client: chromadb.PersistentClient | None = None
_embed_fn: ZhipuEmbeddingFunction | None = None


def _get_client() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=settings.chroma_path)
        log.info("chroma_client_initialized", path=settings.chroma_path)
    return _chroma_client


def _get_embed_fn() -> ZhipuEmbeddingFunction:
    global _embed_fn
    if _embed_fn is None:
        _embed_fn = ZhipuEmbeddingFunction()
    return _embed_fn


def _collection_name(tenant_code: str) -> str:
    code = tenant_code.strip() or "shared"
    # ChromaDB collection names: 3-63 chars, alphanumeric + underscore/hyphen
    safe = "".join(c if c.isalnum() else "_" for c in code)[:40]
    return f"{settings.chroma_collection}_{safe}"


# ── Public API ────────────────────────────────────────────────────────────────

def get_collection(tenant_code: str = "") -> chromadb.Collection:
    """Return (or create) the ChromaDB collection for a tenant."""
    client = _get_client()
    name = _collection_name(tenant_code)
    col = client.get_or_create_collection(
        name=name,
        embedding_function=_get_embed_fn(),
        metadata={"hnsw:space": "cosine"},
    )
    return col


def add_documents(
    chunks: list[str],
    metadatas: list[dict[str, Any]],
    tenant_code: str = "",
) -> int:
    """Embed and store document chunks. Returns number of chunks added."""
    if not chunks:
        return 0
    col = get_collection(tenant_code)
    # Stable deterministic IDs so re-uploading the same file is idempotent
    ids = [
        hashlib.md5(f"{meta.get('source','')}_{meta.get('chunk_index',i)}".encode()).hexdigest()
        for i, meta in enumerate(metadatas)
    ]
    col.upsert(documents=chunks, metadatas=metadatas, ids=ids)
    log.info("chroma_documents_added", tenant=tenant_code or "shared", n=len(chunks))
    return len(chunks)


def search(
    query: str,
    tenant_code: str = "",
    top_k: int | None = None,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Vector search; returns list of {text, source, chunk_index, score} dicts.

    Args:
        query:       Natural-language search query.
        tenant_code: Tenant scope (empty = shared collection).
        top_k:       Max number of results (default from settings).
        filters:     Optional ChromaDB ``where`` clause for metadata filtering.
                     Examples:
                       {"filename": {"$eq": "handbook.pdf"}}
                       {"$and": [{"filename": {"$eq": "policy.pdf"}},
                                 {"chunk_index": {"$gte": 5}}]}
                     Supported operators: $eq $ne $gt $gte $lt $lte $and $or
    """
    k = top_k or settings.rag_top_k
    col = get_collection(tenant_code)
    count = col.count()
    if count == 0:
        return []
    k = min(k, count)

    query_kwargs: dict[str, Any] = {"query_texts": [query], "n_results": k}
    if filters:
        query_kwargs["where"] = filters

    results = col.query(**query_kwargs)
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    output = []
    for doc, meta, dist in zip(docs, metas, distances):
        output.append({
            "text": doc,
            "source": meta.get("filename", "unknown"),
            "chunk_index": meta.get("chunk_index", 0),
            "score": round(1 - dist, 4),   # cosine distance → similarity
        })
    return output


def list_documents(tenant_code: str = "") -> list[dict[str, Any]]:
    """Return distinct filenames + chunk counts stored for a tenant."""
    col = get_collection(tenant_code)
    if col.count() == 0:
        return []
    all_meta = col.get(include=["metadatas"])["metadatas"] or []
    by_file: dict[str, int] = {}
    for m in all_meta:
        fname = m.get("filename", "unknown")
        by_file[fname] = by_file.get(fname, 0) + 1
    return [{"filename": k, "chunks": v} for k, v in sorted(by_file.items())]
