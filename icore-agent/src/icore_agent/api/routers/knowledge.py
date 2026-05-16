"""Knowledge base management endpoints.

POST /api/v1/knowledge/upload    — upload a document (PDF/DOCX/TXT/MD)
GET  /api/v1/knowledge/documents — list uploaded documents for a tenant
DELETE /api/v1/knowledge/documents/{filename} — remove a document
"""

from __future__ import annotations

from icore_agent.lib.logging import get_service_logger
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from ...application.knowledge import SUPPORTED_EXTENSIONS
from ...application.knowledge.service import KnowledgeService
from ..dependencies import get_current_user, get_knowledge_service

log = get_service_logger(__name__)
router = APIRouter()


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
    tenant_code: Annotated[str, Form(
        description="Tenant identifier (leave empty for shared KB)")] = "",
    scope: Annotated[str, Form(
        description="private | organization | shared")] = "organization",
    user: dict = Depends(get_current_user),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> UploadResponse:
    ext = "." + file.filename.rsplit(".", 1)[-1].lower(
    ) if file.filename and "." in file.filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}",
        )

    data = await file.read()
    try:
        service.ensure_file_size(data)
        text = service.parse_document(file.filename or "upload", data)
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except Exception as exc:
        log.error("knowledge_parse_error",
                  filename=file.filename, error=str(exc))
        raise HTTPException(
            status_code=422, detail=f"Failed to parse file: {exc}") from exc

    resolved_tenant = service.resolve_tenant_code(
        user, tenant_code=tenant_code, scope=scope)

    try:
        stored = service.store_document(
            filename=file.filename or "",
            text=text,
            tenant_code=resolved_tenant,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        log.error("knowledge_store_error",
                  filename=file.filename, error=str(exc))
        raise HTTPException(
            status_code=500, detail=f"Failed to store document: {exc}") from exc

    log.info("knowledge_uploaded", filename=file.filename,
             tenant=resolved_tenant or "shared", chunks=stored)
    return UploadResponse(filename=file.filename or "", tenant_code=resolved_tenant, chunks_stored=stored)


@router.get("/documents", response_model=list[DocumentInfo], summary="List uploaded documents")
async def list_knowledge_documents(
    tenant_code: str = "",
    scope: Annotated[str, Query(
        description="private | organization | shared")] = "organization",
    user: dict = Depends(get_current_user),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> list[DocumentInfo]:
    resolved_tenant = service.resolve_tenant_code(
        user, tenant_code=tenant_code, scope=scope)
    docs = service.list_documents(tenant_code=resolved_tenant)
    return [DocumentInfo(**d) for d in docs]


@router.delete("/documents/{filename}", summary="Remove a document from the knowledge base")
async def delete_document(
    filename: str,
    tenant_code: str = "",
    scope: Annotated[str, Query(
        description="private | organization | shared")] = "organization",
    user: dict = Depends(get_current_user),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> dict:
    resolved_tenant = service.resolve_tenant_code(
        user, tenant_code=tenant_code, scope=scope)
    try:
        deleted = service.delete_document(
            filename=filename, tenant_code=resolved_tenant)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    log.info("knowledge_deleted", filename=filename,
             tenant=resolved_tenant or "shared", chunks=deleted)
    return {"deleted": True, "filename": filename, "chunks_removed": deleted}
