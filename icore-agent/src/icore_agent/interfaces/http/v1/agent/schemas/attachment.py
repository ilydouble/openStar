"""Agent attachment schemas."""

from pydantic import BaseModel


class AttachmentInfo(BaseModel):
    filename: str
    mode: str
    uploaded_at: float
    char_count: int | None = None
    ref: str | None = None
    size: int | None = None
    ext: str | None = None
    row_count: int | None = None
    columns: list[dict] | None = None
    preview_md: str | None = None
    preview_error: str | None = None


class AttachResponse(BaseModel):
    filename: str
    char_count: int
    mode: str


class ImageAttachResponse(BaseModel):
    filename: str
    ref: str
    size: int
    mode: str = "image"


class DataAttachResponse(BaseModel):
    filename: str
    ref: str
    size: int
    ext: str
    row_count: int | None = None
    columns: list[dict] = []
    preview_md: str = ""
    preview_error: str = ""
    mode: str = "data"
