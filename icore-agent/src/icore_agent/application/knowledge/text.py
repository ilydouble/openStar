"""Text chunking helpers for knowledge ingestion."""

from __future__ import annotations


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks while preferring whitespace boundaries."""
    if not text.strip():
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        if chunks and len(text) - start <= overlap:
            break
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start, end)
            # Avoid shrinking a chunk too aggressively when the nearest space is
            # too close to the beginning; otherwise short prefixes fragment the text.
            if boundary > start + (size // 2):
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap if end - overlap > start else end
    return chunks
