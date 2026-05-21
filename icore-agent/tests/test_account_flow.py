from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from icore_agent.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _api_data(resp) -> dict:
    """Return the ApiEnvelope data object from a test response."""
    payload = resp.json()
    assert payload["code"] == resp.status_code
    assert payload["message"]
    assert payload["timestamp"]
    return payload["data"]


def _api_message(resp) -> str:
    """Return the ApiEnvelope message from a test response."""
    payload = resp.json()
    assert payload["code"] == resp.status_code
    assert payload["timestamp"]
    return payload["message"]


def _register_trial_direct(client: TestClient, email: str | None = None, name: str = "Trial User") -> dict:
    """在测试中绕过验证码和 IP 限流，直接向 store 注入验证码 + 清理 IP 记录后注册。"""
    from icore_agent.infrastructure.control_plane.json_store import control_plane_store

    email = email or f"trial-{uuid4().hex[:8]}@example.com"
    code = "123456"
    # 注入验证码并清除 127.0.0.1 的 IP 注册记录，使每次测试都能通过
    with control_plane_store._lock:
        data = control_plane_store._load()
        data.setdefault("verification_codes", {})[email.lower()] = {
            "code": code,
            "expires_at": int(time.time()) + 600,
            "ip": "127.0.0.1",
            "timestamp": int(time.time()),
        }
        # 清除测试 IP 的注册记录，让每个测试用例都能独立注册
        data.setdefault("ip_registrations", {}).pop("127.0.0.1", None)
        data.setdefault("ip_registrations", {}).pop("testclient", None)
        control_plane_store._save(data)

    resp = client.post(
        "/api/v1/account/register-trial",
        json={"name": name, "email": email, "verification_code": code},
    )
    assert resp.status_code == 200, resp.json()
    return _api_data(resp)


def _trial_headers(client: TestClient) -> dict[str, str]:
    payload = _register_trial_direct(client)
    return {"Authorization": f"Bearer {payload['access_token']}"}


def test_register_trial_and_fetch_account_profile(client: TestClient):
    email = f"trial-{uuid4().hex[:8]}@example.com"
    payload = _register_trial_direct(client, email=email)
    assert payload["access_token"]
    assert payload["user"]["plan"] == "free"

    me = client.get("/api/v1/account/me",
                    headers={"Authorization": f"Bearer {payload['access_token']}"})
    assert me.status_code == 200
    assert _api_data(me)["email"] == email


def test_email_login_persists_token_for_protected_routes(client: TestClient):
    """Login must save the token to the control-plane store (same as register-trial)."""
    email = f"login-{uuid4().hex[:8]}@example.com"
    _register_trial_direct(client, email=email)

    code = "888888"

    from icore_agent.infrastructure.control_plane.json_store import control_plane_store

    with control_plane_store._lock:
        data = control_plane_store._load()
        data.setdefault("verification_codes", {})[email.lower()] = {
            "code": code,
            "expires_at": int(time.time()) + 600,
            "ip": "127.0.0.1",
            "timestamp": int(time.time()),
        }
        control_plane_store._save(data)

    login = client.post(
        "/api/v1/account/login",
        json={"email": email, "verification_code": code},
    )
    assert login.status_code == 200, login.text
    body = _api_data(login)
    token = body["access_token"]
    assert token

    me = client.get("/api/v1/account/me",
                    headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text
    assert _api_data(me)["email"] == email


def test_register_trial_requires_verification_code(client: TestClient):
    email = f"trial-{uuid4().hex[:8]}@example.com"
    # 不提供验证码，应该被 Pydantic 拒绝
    resp = client.post(
        "/api/v1/account/register-trial",
        json={"name": "Trial User", "email": email},
    )
    assert resp.status_code == 422  # 缺少 verification_code 字段


def test_register_trial_wrong_code_rejected(client: TestClient):
    email = f"trial-{uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/v1/account/register-trial",
        json={"name": "Trial User", "email": email,
              "verification_code": "000000"},
    )
    assert resp.status_code == 400
    assert _api_message(resp) == "Invalid or expired verification code"


def test_email_login_unregistered_email_returns_english_message(client: TestClient):
    email = f"missing-{uuid4().hex[:8]}@example.com"
    code = "654321"

    from icore_agent.infrastructure.control_plane.json_store import control_plane_store

    with control_plane_store._lock:
        data = control_plane_store._load()
        data.setdefault("verification_codes", {})[email.lower()] = {
            "code": code,
            "expires_at": int(time.time()) + 600,
            "ip": "127.0.0.1",
            "timestamp": int(time.time()),
        }
        control_plane_store._save(data)

    resp = client.post(
        "/api/v1/account/login",
        json={"email": email, "verification_code": code},
    )
    assert resp.status_code == 404
    assert _api_message(resp) == (
        "This email is not registered. Please sign up for a trial account first."
    )


def test_send_verification_code_endpoint(client: TestClient):
    email = f"trial-{uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/v1/account/send-verification-code",
        json={"email": email},
    )
    assert resp.status_code == 200
    assert _api_data(resp)["success"] is True


@patch("icore_agent.infrastructure.control_plane.json_store.settings.debug", True)
@patch("icore_agent.infrastructure.control_plane.json_store._send_verification_email", return_value=False)
def test_send_verification_code_falls_back_in_debug_when_email_delivery_fails(mock_send, client: TestClient):
    from icore_agent.infrastructure.control_plane.json_store import control_plane_store

    with control_plane_store._lock:
        data = control_plane_store._load()
        data["verification_codes"] = {}
        control_plane_store._save(data)

    email = f"trial-{uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/v1/account/send-verification-code",
        json={"email": email},
    )
    assert resp.status_code == 200
    body = _api_data(resp)
    assert body["success"] is True
    assert "Verification code sent to" in body["message"]


@patch("icore_agent.interfaces.http.v1.agent.handlers.chat.create_orchestrator")
@patch("icore_agent.interfaces.http.v1.agent.handlers.chat.memory")
def test_chat_requires_account_token(mock_memory, mock_create_orch, client: TestClient):
    mock_memory.get_context = AsyncMock(
        return_value=(None, [], None, False, [], []))
    mock_memory.append_message = AsyncMock()
    mock_create_orch.return_value = MagicMock(return_value="secured reply")

    unauthorized = client.post(
        "/api/v1/agent/chat",
        json={"message": "Hello", "stream": False,
              "session_id": "secure-session"},
    )
    assert unauthorized.status_code == 401

    headers = _trial_headers(client)
    authorized = client.post(
        "/api/v1/agent/chat",
        headers=headers,
        json={"message": "Hello", "stream": False,
              "session_id": "secure-session"},
    )
    assert authorized.status_code == 200
    assert _api_data(authorized)["reply"] == "secured reply"


def test_can_update_byok_and_read_plan_summary(client: TestClient):
    headers = _trial_headers(client)

    byok = client.post(
        "/api/v1/account/billing/byok",
        headers=headers,
        json={"api_key": "demo-key", "api_base": "https://relay.example.com",
              "model": "openai/gpt-4o-mini"},
    )
    assert byok.status_code == 200
    assert _api_data(byok)["enabled"] is True

    plan = client.get("/api/v1/account/billing/plan", headers=headers)
    assert plan.status_code == 200
    payload = _api_data(plan)
    assert payload["plan"] == "free"
    assert payload["byok"]["enabled"] is True


@patch("icore_agent.interfaces.http.v1.agent.handlers.session.memory")
def test_can_fetch_session_state(mock_memory, client: TestClient):
    user_payload = _register_trial_direct(client)
    headers = {"Authorization": f"Bearer {user_payload['access_token']}"}
    from icore_agent.application.chat import ChatHistoryService

    ChatHistoryService().ensure_owned_session(
        "demo-session",
        user_payload["user"]["id"],
        title="Demo session",
    )
    mock_memory.get_context = AsyncMock(
        return_value=(
            "Summary text",
            [
                {"role": "user", "content": "Research this market"},
                {"role": "assistant", "content": "Here is the review"},
            ],
        )
    )

    resp = client.get("/api/v1/agent/session/demo-session", headers=headers)
    assert resp.status_code == 200
    payload = _api_data(resp)
    assert payload["session_id"] == "demo-session"
    assert payload["summary"] == "Summary text"
    assert len(payload["messages"]) == 2
    assert payload["attachments"] == []


def test_can_fetch_admin_overview(client: TestClient):
    headers = _trial_headers(client)
    overview = client.get("/api/v1/account/admin/overview", headers=headers)
    assert overview.status_code == 200
    payload = _api_data(overview)
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
    payload = _api_data(listing)
    assert payload["projects"][0]["id"] == "weekly-review"
    assert payload["projects"][0]["sessions_count"] == 1
    assert payload["recent_sessions"][0]["session_id"] == "session-1"


def test_can_read_and_update_team_profile(client: TestClient):
    headers = _trial_headers(client)
    team = client.get("/api/v1/account/team", headers=headers)
    assert team.status_code == 200
    payload = _api_data(team)
    assert payload["organization"]["id"]
    assert payload["members"][0]["role"] == "owner"

    updated = client.post(
        "/api/v1/account/team/rename",
        headers=headers,
        json={"organization_name": "Stellar Ops"},
    )
    assert updated.status_code == 200
    assert _api_data(updated)["organization"]["name"] == "Stellar Ops"

    member = client.post(
        "/api/v1/account/team/members",
        headers=headers,
        json={"name": "Ops User", "email": "ops@example.com", "role": "editor"},
    )
    assert member.status_code == 200
    assert _api_data(member)["member"]["email"] == "ops@example.com"


@patch("icore_agent.interfaces.http.v1.dependencies.knowledge_service._add_documents")
@patch("icore_agent.interfaces.http.v1.dependencies.knowledge_service.parse_document")
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
    tenant_code = _api_data(resp)["tenant_code"]
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
    payload = _api_data(resp)
    assert payload["lead"]["email"] == "lead@example.com"
    assert payload["lead"]["intent"] == "enterprise"
