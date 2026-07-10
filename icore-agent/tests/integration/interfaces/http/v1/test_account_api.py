from __future__ import annotations

import time
from unittest.mock import patch
from uuid import uuid4

import pytest

from icore_agent.main import app
from tests.integration.interfaces.http.v1._account_support import (
    register_trial_direct as _register_trial_direct,
)
from tests.integration.interfaces.http.v1._account_support import (
    trial_headers as _trial_headers,
)
from tests.support.http import (
    ASGISyncTestClient,
)
from tests.support.http import (
    api_data as _api_data,
)
from tests.support.http import (
    api_message as _api_message,
)


@pytest.fixture()
def client():
    return ASGISyncTestClient(app)


def test_register_trial_and_fetch_account_profile(client: ASGISyncTestClient):
    email = f"trial-{uuid4().hex[:8]}@example.com"
    payload = _register_trial_direct(client, email=email)
    assert payload["access_token"]
    assert payload["user"]["plan"] == "trial"

    me = client.get("/api/v1/account/me",
                    headers={"Authorization": f"Bearer {payload['access_token']}"})
    assert me.status_code == 200
    assert _api_data(me)["email"] == email


def test_email_login_persists_token_for_protected_routes(client: ASGISyncTestClient):
    """Login must save the token to the control-plane store (same as register-trial)."""
    email = f"login-{uuid4().hex[:8]}@example.com"
    _register_trial_direct(client, email=email)

    code = "888888"

    from icore_agent.contexts.account.infrastructure.control_plane.json_store import (
        control_plane_store,
    )

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
    assert login.status_code == 200, login.TEXT
    body = _api_data(login)
    token = body["access_token"]
    assert token

    me = client.get("/api/v1/account/me",
                    headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.TEXT
    assert _api_data(me)["email"] == email


def test_register_trial_requires_verification_code(client: ASGISyncTestClient):
    email = f"trial-{uuid4().hex[:8]}@example.com"
    # 不提供验证码，应该被 Pydantic 拒绝
    resp = client.post(
        "/api/v1/account/register-trial",
        json={"name": "Trial User", "email": email},
    )
    assert resp.status_code == 422  # 缺少 verification_code 字段


def test_register_trial_wrong_code_rejected(client: ASGISyncTestClient):
    email = f"trial-{uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/v1/account/register-trial",
        json={"name": "Trial User", "email": email,
              "verification_code": "000000"},
    )
    assert resp.status_code == 400
    assert _api_message(resp) == "Invalid or expired verification code"


def test_email_login_unregistered_email_returns_english_message(
    client: ASGISyncTestClient,
):
    email = f"missing-{uuid4().hex[:8]}@example.com"
    code = "654321"

    from icore_agent.contexts.account.infrastructure.control_plane.json_store import (
        control_plane_store,
    )

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


def test_send_verification_code_endpoint(client: ASGISyncTestClient):
    email = f"trial-{uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/v1/account/send-verification-code",
        json={"email": email},
    )
    assert resp.status_code == 200
    assert _api_data(resp)["success"] is True


def test_send_login_verification_code_rejects_unregistered_email(
    client: ASGISyncTestClient,
):
    """Login verification must fail before sending when the email is unknown."""
    email = f"missing-{uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/v1/account/send-verification-code",
        json={"email": email, "purpose": "login"},
    )
    assert resp.status_code == 404
    assert _api_message(resp) == (
        "This email is not registered. Please sign up for a trial account first."
    )


def test_send_login_verification_code_allows_registered_email(
    client: ASGISyncTestClient,
):
    """Registered users should receive login verification codes."""
    email = f"login-{uuid4().hex[:8]}@example.com"
    _register_trial_direct(client, email=email)

    resp = client.post(
        "/api/v1/account/send-verification-code",
        json={"email": email, "purpose": "login"},
    )
    assert resp.status_code == 200
    assert _api_data(resp)["success"] is True


def test_send_register_verification_code_rejects_registered_email(
    client: ASGISyncTestClient,
):
    """Registration verification must fail before sending when the email is taken."""
    email = f"existing-{uuid4().hex[:8]}@example.com"
    _register_trial_direct(client, email=email)

    resp = client.post(
        "/api/v1/account/send-verification-code",
        json={"email": email, "purpose": "register"},
    )
    assert resp.status_code == 400
    assert _api_message(resp) == (
        "This email is already registered. Please use email login instead."
    )


@patch("icore_agent.contexts.account.infrastructure.control_plane.json_store.settings.debug", True)
@patch("icore_agent.contexts.account.infrastructure.control_plane.json_store._send_verification_email", return_value=False)
def test_send_verification_code_falls_back_in_debug_when_email_delivery_fails(
    mock_send,
    client: ASGISyncTestClient,
):
    from icore_agent.contexts.account.infrastructure.control_plane.json_store import (
        control_plane_store,
    )

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


def test_can_update_byok_and_read_plan_summary(client: ASGISyncTestClient):
    headers = _trial_headers(client)

    byok = client.post(
        "/api/v1/account/billing/byok",
        headers=headers,
        json={"api_key": "demo-key", "api_base": "https://relay.example.com",
              "model": "openai/gpt-4o-mini"},
    )
    assert byok.status_code == 200
    byok_payload = _api_data(byok)
    assert byok_payload["enabled"] is True
    assert byok_payload["api_key"] == "****-key"

    plan = client.get("/api/v1/account/billing/plan", headers=headers)
    assert plan.status_code == 200
    payload = _api_data(plan)
    assert payload["plan"] == "trial"
    assert payload["byok"]["enabled"] is True
    assert payload["byok"]["api_key"] == "****-key"

    me = client.get("/api/v1/account/me", headers=headers)
    assert me.status_code == 200
    me_payload = _api_data(me)
    assert me_payload["byok"]["api_key"] == "****-key"


def test_admin_overview_denied_for_owner_only_trial_user(
    client: ASGISyncTestClient,
):
    """Trial users keep owner role but cannot access platform admin overview."""
    headers = _trial_headers(client)
    overview = client.get("/api/v1/account/admin/overview", headers=headers)
    assert overview.status_code == 403


def test_admin_overview_allowed_for_platform_admin(
    client: ASGISyncTestClient,
):
    """Users granted the admin role can access platform admin overview."""
    email = f"admin-{uuid4().hex[:8]}@example.com"
    payload = _register_trial_direct(client, email=email)
    _grant_platform_admin_role(email)

    overview = client.get(
        "/api/v1/account/admin/overview",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )
    assert overview.status_code == 200
    body = _api_data(overview)
    assert body["users"]["total"] >= 1
    assert "usage" in body
    assert "heavy_users" in body


def _grant_platform_admin_role(email: str) -> None:
    """Append the platform admin role to one persisted user profile."""
    from dataclasses import replace

    from icore_agent.contexts.account.infrastructure.persistence.users.sqlalchemy_repository import (
        SqlAlchemyUserRepository,
    )
    from icore_agent.infrastructure.persistence.sqlalchemy.sync_session import (
        sync_session_scope,
    )

    with sync_session_scope() as session:
        repo = SqlAlchemyUserRepository(session)
        user = repo.get_by_email(email)
        assert user is not None
        roles = list(user.roles or ["owner"])
        if "admin" not in roles:
            roles.append("admin")
        repo.save(replace(user, roles=roles))


def test_can_sync_and_list_projects(client: ASGISyncTestClient):
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


def test_can_read_and_update_team_profile(client: ASGISyncTestClient):
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


def test_public_enterprise_lead_capture(client: ASGISyncTestClient):
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
