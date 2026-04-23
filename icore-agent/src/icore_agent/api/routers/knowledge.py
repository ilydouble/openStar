"""Knowledge base management endpoints.

POST /api/v1/knowledge/upload    — upload a document (PDF/DOCX/TXT/MD)
GET  /api/v1/knowledge/documents — list uploaded documents for a tenant
DELETE /api/v1/knowledge/documents/{filename} — remove a document
"""

from __future__ import annotations

import io
import re
import structlog
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ...memory.chroma_store import add_documents, list_documents, get_collection
from ...config import settings

log = structlog.get_logger()
router = APIRouter()

SUPPORTED_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
}
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


# ── Document parsing ──────────────────────────────────────────────────────────

def _parse_txt(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _parse_pdf(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _parse_docx(data: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _parse_file(filename: str, data: bytes) -> str:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == ".pdf":
        return _parse_pdf(data)
    if ext == ".docx":
        return _parse_docx(data)
    return _parse_txt(data)   # .txt / .md / fallback


# ── Chunking ──────────────────────────────────────────────────────────────────

def _chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """Split text into overlapping character-level chunks, breaking on whitespace."""
    if not text.strip():
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        # Try to break on whitespace boundary
        if end < len(text):
            boundary = text.rfind(" ", start, end)
            if boundary > start:
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap if end - overlap > start else end
    return chunks


# ── Request / Response schemas ────────────────────────────────────────────────

class UploadResponse(BaseModel):
    filename: str
    tenant_code: str
    chunks_stored: int


class DocumentInfo(BaseModel):
    filename: str
    chunks: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse, summary="Upload a document to the knowledge base")
async def upload_document(
    file: Annotated[UploadFile, File(description="PDF, DOCX, TXT, or MD file")],
    tenant_code: Annotated[str, Form(description="Tenant identifier (leave empty for shared KB)")] = "",
) -> UploadResponse:
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}",
        )

    data = await file.read()
    if len(data) > settings.file_ops_max_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.file_ops_max_size_mb} MB limit")

    try:
        text = _parse_file(file.filename or "upload", data)
    except Exception as exc:
        log.error("knowledge_parse_error", filename=file.filename, error=str(exc))
        raise HTTPException(status_code=422, detail=f"Failed to parse file: {exc}") from exc

    chunks = _chunk_text(text, settings.rag_chunk_size, settings.rag_chunk_overlap)
    if not chunks:
        raise HTTPException(status_code=422, detail="File appears to be empty or unreadable")

    metadatas = [
        {"filename": file.filename, "chunk_index": i, "source": file.filename}
        for i in range(len(chunks))
    ]

    try:
        stored = add_documents(chunks=chunks, metadatas=metadatas, tenant_code=tenant_code)
    except Exception as exc:
        log.error("knowledge_store_error", filename=file.filename, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Failed to store document: {exc}") from exc

    log.info("knowledge_uploaded", filename=file.filename, tenant=tenant_code or "shared", chunks=stored)
    return UploadResponse(filename=file.filename or "", tenant_code=tenant_code, chunks_stored=stored)


@router.get("/documents", response_model=list[DocumentInfo], summary="List uploaded documents")
async def list_knowledge_documents(tenant_code: str = "") -> list[DocumentInfo]:
    docs = list_documents(tenant_code=tenant_code)
    return [DocumentInfo(**d) for d in docs]


@router.delete("/documents/{filename}", summary="Remove a document from the knowledge base")
async def delete_document(filename: str, tenant_code: str = "") -> dict:
    col = get_collection(tenant_code=tenant_code)
    # Get all chunk IDs for this filename
    results = col.get(where={"filename": filename}, include=["metadatas"])
    ids = results.get("ids") or []
    if not ids:
        raise HTTPException(status_code=404, detail=f"Document '{filename}' not found")
    col.delete(ids=ids)
    log.info("knowledge_deleted", filename=filename, tenant=tenant_code or "shared", chunks=len(ids))
    return {"deleted": True, "filename": filename, "chunks_removed": len(ids)}
