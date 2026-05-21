"""Knowledge document schemas."""

from pydantic import BaseModel


class UploadResponse(BaseModel):
    filename: str
    tenant_code: str
    chunks_stored: int


class DocumentInfo(BaseModel):
    filename: str
    chunks: int
