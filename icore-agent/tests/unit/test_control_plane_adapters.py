from __future__ import annotations

from icore_agent.infrastructure.control_plane.adapters import (
    ControlPlaneBillingRepository,
    ControlPlaneBillingSummaryRepository,
    ControlPlaneIdentityRepository,
    ControlPlaneLeadRepository,
    ControlPlaneProjectRepository,
    ControlPlaneRegistrationRepository,
    ControlPlaneTeamRepository,
    ControlPlaneUsageRepository,
    ControlPlaneVerificationRepository,
)


class FakeControlPlaneStore:
    """Store double used to verify adapter delegation."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    def get_user_by_token(self, token: str):
        self.calls.append(("get_user_by_token", (token,), {}))
        return {"id": "u1"} if token == "tok" else None

    def send_verification_code(self, email: str, client_ip: str):
        self.calls.append(("send_verification_code", (email, client_ip), {}))
        return True, "sent"

    def verify_code(self, email: str, code: str):
        self.calls.append(("verify_code", (email, code), {}))
        return True

    def get_user_by_email(self, email: str):
        self.calls.append(("get_user_by_email", (email,), {}))
        return {"id": "u1", "email": email}

    def issue_token_for_user(self, user_id: str):
        self.calls.append(("issue_token_for_user", (user_id,), {}))
        return f"token:{user_id}"

    def check_ip_registration_limit(self, client_ip: str):
        self.calls.append(("check_ip_registration_limit", (client_ip,), {}))
        return True

    def register_trial(self, name: str, email: str, client_ip: str):
        self.calls.append(("register_trial", (name, email, client_ip), {}))
        return {"id": "u1"}, "tok"

    def create_lead(self, **payload):
        self.calls.append(("create_lead", (), payload))
        return payload

    def get_team_profile(self, user_id: str):
        self.calls.append(("get_team_profile", (user_id,), {}))
        return {"organization": {"id": "org-1"}}

    def rename_organization(self, user_id: str, organization_name: str):
        self.calls.append(("rename_organization", (user_id, organization_name), {}))
        return {"organization": {"name": organization_name}}

    def add_team_member(self, user_id: str, **payload):
        self.calls.append(("add_team_member", (user_id,), payload))
        return payload

    def update_knowledge_scope(self, user_id: str, scope: str):
        self.calls.append(("update_knowledge_scope", (user_id, scope), {}))
        return {"scope": scope}

    def sync_project_session(self, **payload):
        self.calls.append(("sync_project_session", (), payload))
        return payload

    def list_projects(self, user_id: str):
        self.calls.append(("list_projects", (user_id,), {}))
        return {"projects": []}

    def get_plan_summary(self, user_id: str):
        self.calls.append(("get_plan_summary", (user_id,), {}))
        return {"plan": "free"}

    def update_byok(self, user_id: str, api_key: str, api_base: str, model: str):
        self.calls.append(("update_byok", (user_id, api_key, api_base, model), {}))
        return {"enabled": True}

    def update_user_plan(self, **payload):
        self.calls.append(("update_user_plan", (), payload))
        return {"plan": payload["new_plan"], "plan_label": payload["new_plan"].title()}

    def check_quota(self, user_id: str, resource: str):
        self.calls.append(("check_quota", (user_id, resource), {}))
        return True, None

    def consume_quota(self, user_id: str, resource: str):
        self.calls.append(("consume_quota", (user_id, resource), {}))

    def usage_summary(self, user_id: str):
        self.calls.append(("usage_summary", (user_id,), {}))
        return {"user_id": user_id}

    def admin_overview(self):
        self.calls.append(("admin_overview", (), {}))
        return {"users": {"total": 1}}

    def record_usage_event(self, **payload):
        self.calls.append(("record_usage_event", (), payload))


def test_split_account_adapters_delegate_to_the_expected_store_methods():
    store = FakeControlPlaneStore()
    identity_repo = ControlPlaneIdentityRepository(store)
    verification_repo = ControlPlaneVerificationRepository(store)
    registration_repo = ControlPlaneRegistrationRepository(store)
    lead_repo = ControlPlaneLeadRepository(store)
    team_repo = ControlPlaneTeamRepository(store)
    project_repo = ControlPlaneProjectRepository(store)
    billing_summary_repo = ControlPlaneBillingSummaryRepository(store)

    assert identity_repo.get_user_by_token("tok") == {"id": "u1"}
    verification_repo.send_verification_code("a@example.com", "127.0.0.1")
    registration_repo.register_trial("Trial", "a@example.com", "127.0.0.1")
    lead_repo.create_lead(email="lead@example.com")
    team_repo.get_team_profile("u1")
    project_repo.sync_project_session(user_id="u1", project_id="p1")
    billing_summary_repo.get_plan_summary("u1")

    assert [name for name, *_ in store.calls] == [
        "get_user_by_token",
        "send_verification_code",
        "register_trial",
        "create_lead",
        "get_team_profile",
        "sync_project_session",
        "get_plan_summary",
    ]


def test_usage_and_billing_adapters_delegate_to_control_plane_store():
    store = FakeControlPlaneStore()
    usage_repo = ControlPlaneUsageRepository(store)
    billing_repo = ControlPlaneBillingRepository(store)

    usage_repo.record_usage_event(user_id="u1", session_id="s1", total_tokens=42)
    result = billing_repo.update_user_plan(
        user_id="u1",
        new_plan="team",
        byok_enabled=False,
        byok_api_key="",
        byok_api_base="",
        byok_model="",
    )

    assert result["plan"] == "team"
    assert [name for name, *_ in store.calls] == ["record_usage_event", "update_user_plan"]
