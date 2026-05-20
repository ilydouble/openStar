from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from icore_agent.application.knowledge.parsers import SUPPORTED_EXTENSIONS, parse_file
from icore_agent.application.knowledge.service import KnowledgeService
from icore_agent.application.knowledge.text import chunk_text


def test_chunk_text_splits_on_boundaries():
    chunks = chunk_text("alpha beta gamma delta", size=10, overlap=2)

    assert chunks == ["alpha beta", "ta gamma", "ma delta"]


def test_parse_file_uses_pdf_reader():
    fake_reader = SimpleNamespace(
        pages=[
            SimpleNamespace(extract_text=lambda: "one"),
            SimpleNamespace(extract_text=lambda: "two"),
        ]
    )

    with patch("icore_agent.application.knowledge.parsers.PdfReader", return_value=fake_reader):
        parsed = parse_file("report.pdf", b"%PDF")

    assert parsed == "one\ntwo"


def test_supported_extensions_include_plain_docs():
    assert {".pdf", ".docx", ".txt", ".md"} <= SUPPORTED_EXTENSIONS


@pytest.mark.parametrize(
    ("tenant_code", "scope", "expected"),
    [
        ("custom", "organization", "custom"),
        ("", "private", "user-1"),
        ("", "organization", "org:org-1"),
        ("", "shared", ""),
    ],
)
def test_knowledge_service_resolves_tenant_code(tenant_code: str, scope: str, expected: str):
    service = KnowledgeService(
        add_documents=lambda **_: 0,
        list_documents=lambda **_: [],
        get_collection=lambda **_: None,
        rag_chunk_size=10,
        rag_chunk_overlap=1,
        file_size_limit_mb=5,
    )

    resolved = service.resolve_tenant_code(
        {"id": "user-1", "organization_id": "org-1"},
        tenant_code=tenant_code,
        scope=scope,
    )

    assert resolved == expected
