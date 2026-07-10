"""Integration tests for composed knowledge HTTP routes."""

from unittest.mock import patch

import pytest

from icore_agent.main import app
from tests.integration.interfaces.http.v1._account_support import trial_headers
from tests.support.http import ASGISyncTestClient, api_data


@pytest.fixture()
def client() -> ASGISyncTestClient:
    """Return an in-process client for the complete backend application."""
    return ASGISyncTestClient(app)


@patch("icore_agent.interfaces.http.v1.dependencies.knowledge_service._add_documents")
@patch("icore_agent.interfaces.http.v1.dependencies.knowledge_service.parse_document")
def test_knowledge_upload_can_use_organization_scope(
    mock_parse,
    mock_add_documents,
    client: ASGISyncTestClient,
) -> None:
    """Knowledge uploads should resolve organization tenancy through the API."""
    headers = trial_headers(client)
    mock_parse.return_value = "Knowledge base content"
    mock_add_documents.return_value = 1

    response = client.post(
        "/api/v1/knowledge/upload",
        headers=headers,
        data={"scope": "organization"},
        files={"file": ("kb.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 200
    assert api_data(response)["tenant_code"].startswith("org:")
