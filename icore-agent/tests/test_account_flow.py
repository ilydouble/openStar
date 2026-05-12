from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from icore_agent.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _trial_headers(client: TestClient) -> dict[str, str]:
    email = f"trial-{uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/v1/account/register-trial",
        json={"name": "Trial User", "email": email},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_register_trial_and_fetch_account_profile(client: TestClient):
    email = f"trial-{uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/v1/account/register-trial",
        json={"name": "Trial User", "email": email},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["access_token"]
    assert payload["user"]["plan"] == "trial"

    me = client.get("/api/v1/account/me", headers={"Authorization": f"Bearer {payload['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == email


@patch("icore_agent.api.routers.agent.create_orchestrator")
@patch("icore_agent.api.routers.agent.memory")
def test_chat_requires_account_token(mock_memory, mock_create_orch, client: TestClient):
    mock_memory.get_context = AsyncMock(return_value=(None, [], None, False, [], []))
    mock_memory.append_message = AsyncMock()
    mock_create_orch.return_value = MagicMock(return_value="secured reply")

    unauthorized = client.post(
        "/api/v1/agent/chat",
        json={"message": "Hello", "stream": False, "session_id": "secure-session"},
    )
    assert unauthorized.status_code == 401

    headers = _trial_headers(client)
    authorized = client.post(
        "/api/v1/agent/chat",
        headers=headers,
        json={"message": "Hello", "stream": False, "session_id": "secure-session"},
    )
    assert authorized.status_code == 200
    assert authorized.json()["reply"] == "secured reply"


def test_can_update_byok_and_read_plan_summary(client: TestClient):
    headers = _trial_headers(client)

    byok = client.post(
        "/api/v1/account/billing/byok",
        headers=headers,
        json={"api_key": "demo-key", "api_base": "https://relay.example.com", "model": "openai/gpt-4o-mini"},
    )
    assert byok.status_code == 200
    assert byok.json()["enabled"] is True

    plan = client.get("/api/v1/account/billing/plan", headers=headers)
    assert plan.status_code == 200
    payload = plan.json()
    assert payload["plan"] == "trial"
    assert payload["byok"]["enabled"] is True


@patch("icore_agent.api.routers.agent.attachments")
@patch("icore_agent.api.routers.agent.memory")
def test_can_fetch_session_state(mock_memory, mock_attachments, client: TestClient):
    headers = _trial_headers(client)
    mock_memory.get_context = AsyncMock(
        return_value=(
            "Summary text",
            [
                {"role": "user", "content": "Research this market"},
                {"role": "assistant", "content": "Here is the review"},
            ],
        )
    )
    mock_attachments.list_info = AsyncMock(
        return_value=[
            {"filename": "brief.pdf", "mode": "rag", "uploaded_at": 123.0},
        ]
    )

    resp = client.get("/api/v1/agent/session/demo-session", headers=headers)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["session_id"] == "demo-session"
    assert payload["summary"] == "Summary text"
    assert len(payload["messages"]) == 2
    assert payload["attachments"][0]["filename"] == "brief.pdf"


def test_can_fetch_admin_overview(client: TestClient):
    headers = _trial_headers(client)
    overview = client.get("/api/v1/account/admin/overview", headers=headers)
    assert overview.status_code == 200
    payload = overview.json()
    assert payload["users"]["total"] >= 1
    assert "usage" in payload
    assert "heavy_users" in payload


def test_can_sync_and_list_projects(client: TestClient):
    headers = _trial_headers(client)
    sync_resp = client.post(
        "/api/v1/account/projects/sync",
        headers=headers,
        json={
            "project_id": "weekly-review",
            "project_title": "Weekly Review Workflow",
            "scenario_id": "data",
            "session_id": "session-1",
            "session_title": "Week 19 review",
            "session_subtitle": "KPIs and next actions",
            "attachment_count": 2,
        },
    )
    assert sync_resp.status_code == 200
    listing = client.get("/api/v1/account/projects", headers=headers)
    assert listing.status_code == 200
    payload = listing.json()
    assert payload["projects"][0]["id"] == "weekly-review"
    assert payload["projects"][0]["sessions_count"] == 1
    assert payload["recent_sessions"][0]["session_id"] == "session-1"


def test_can_read_and_update_team_profile(client: TestClient):
    headers = _trial_headers(client)
    team = client.get("/api/v1/account/team", headers=headers)
    assert team.status_code == 200
    payload = team.json()
    assert payload["organization"]["id"]
    assert payload["members"][0]["role"] == "owner"

    updated = client.post(
        "/api/v1/account/team/rename",
        headers=headers,
        json={"organization_name": "Stellar Ops"},
    )
    assert updated.status_code == 200
    assert updated.json()["organization"]["name"] == "Stellar Ops"

    member = client.post(
        "/api/v1/account/team/members",
        headers=headers,
        json={"name": "Ops User", "email": "ops@example.com", "role": "editor"},
    )
    assert member.status_code == 200
    assert member.json()["member"]["email"] == "ops@example.com"


@patch("icore_agent.api.routers.knowledge.add_documents")
@patch("icore_agent.api.routers.knowledge._parse_file")
def test_knowledge_upload_can_use_organization_scope(mock_parse, mock_add_documents, client: TestClient):
    headers = _trial_headers(client)
    mock_parse.return_value = "Knowledge base content"
    mock_add_documents.return_value = 1

    resp = client.post(
        "/api/v1/knowledge/upload",
        headers=headers,
        data={"scope": "organization"},
        files={"file": ("kb.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 200
    tenant_code = resp.json()["tenant_code"]
    assert tenant_code.startswith("org:")


def test_public_enterprise_lead_capture(client: TestClient):
    resp = client.post(
        "/api/v1/account/leads",
        json={
            "name": "Sales Lead",
            "email": "lead@example.com",
            "company": "Stellar Mesh",
            "team_size": "11-50",
            "use_case": "Need enterprise workflow delivery",
            "needs_byok": True,
            "needs_private_deploy": False,
            "source": "enterprise-page",
            "intent": "enterprise",
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["lead"]["email"] == "lead@example.com"
    assert payload["lead"]["intent"] == "enterprise"
