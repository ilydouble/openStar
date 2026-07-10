"""Integration tests for composed backend health routes."""

import pytest

from icore_agent.main import app
from tests.support.http import ASGISyncTestClient, api_data


@pytest.fixture()
def client() -> ASGISyncTestClient:
    """Return an in-process client for the complete backend application."""
    return ASGISyncTestClient(app)


def test_health_returns_ok(client: ASGISyncTestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = api_data(response)
    assert data["status"] == "ok"
    assert "version" in data


def test_ready_returns_ready(client: ASGISyncTestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert api_data(response)["status"] == "ready"
