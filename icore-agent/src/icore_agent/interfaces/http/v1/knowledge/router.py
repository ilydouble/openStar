"""Knowledge API router."""

from fastapi import APIRouter, Depends

from ..dependencies import get_current_user
from .handlers import delete_document, list_knowledge_documents, upload_document
from .schemas import DocumentInfo, UploadResponse

router = APIRouter(
    prefix="/api/v1/knowledge",
    tags=["knowledge"],
    dependencies=[Depends(get_current_user)],
)

router.post(
    "/upload",
    response_model=UploadResponse,
    summary="Upload a document to the knowledge base",
)(upload_document)
router.get(
    "/documents",
    response_model=list[DocumentInfo],
    summary="List uploaded documents",
)(list_knowledge_documents)
router.delete(
    "/documents/{filename}",
    summary="Remove a document from the knowledge base",
)(delete_document)
