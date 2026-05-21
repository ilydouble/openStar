"""File parsing helpers shared by knowledge and user file workflows."""

from __future__ import annotations

import io

from docx import Document
from pypdf import PdfReader

SUPPORTED_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
}
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


def parse_txt(data: bytes) -> str:
    """Decode plain text input using a lossy UTF-8 fallback."""
    return data.decode("utf-8", errors="replace")


def parse_pdf(data: bytes) -> str:
    """Extract text from a PDF payload page by page."""
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def parse_docx(data: bytes) -> str:
    """Extract non-empty paragraphs from a DOCX payload."""
    doc = Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def parse_file(filename: str, data: bytes) -> str:
    """Parse one supported document into plain text for downstream indexing."""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == ".pdf":
        return parse_pdf(data)
    if ext == ".docx":
        return parse_docx(data)
    return parse_txt(data)
