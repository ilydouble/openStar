from __future__ import annotations

from icore_agent.application.account.service import AccountService


class FakeAccountStore:
    """Minimal store double used to verify account service orchestration."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []
        self.user_by_token = {"tok": {"id": "u1", "roles": ["owner"]}}

    def get_user_by_token(self, token: str) -> dict | None:
        self.calls.append(("get_user_by_token", (token,), {}))
        return self.user_by_token.get(token)

    def send_verification_code(self, email: str, client_ip: str) -> tuple[bool, str]:
        self.calls.append(("send_verification_code", (email, client_ip), {}))
        return True, f"sent:{email}:{client_ip}"

    def verify_code(self, email: str, code: str) -> bool:
        self.calls.append(("verify_code", (email, code), {}))
        return code == "123456"

    def get_user_by_email(self, email: str) -> dict | None:
        self.calls.append(("get_user_by_email", (email,), {}))
        return None

    def check_ip_registration_limit(self, client_ip: str) -> bool:
        self.calls.append(("check_ip_registration_limit", (client_ip,), {}))
        return True

    def register_trial(self, name: str, email: str, client_ip: str) -> tuple[dict, str]:
        self.calls.append(("register_trial", (name, email, client_ip), {}))
        return {"id": "u1", "email": email, "plan": "free"}, "tok"

    def issue_token_for_user(self, user_id: str) -> str:
        self.calls.append(("issue_token_for_user", (user_id,), {}))
        return f"issued:{user_id}"

    def create_lead(self, **payload) -> dict:
        self.calls.append(("create_lead", (), payload))
        return payload | {"id": "lead-1"}

    def usage_summary(self, user_id: str) -> dict:
        self.calls.append(("usage_summary", (user_id,), {}))
        return {"user_id": user_id}

    def admin_overview(self) -> dict:
        self.calls.append(("admin_overview", (), {}))
        return {"users": {"total": 1}}

    def get_plan_summary(self, user_id: str) -> dict:
        self.calls.append(("get_plan_summary", (user_id,), {}))
        return {"user_id": user_id, "plan": "free"}

    def update_byok(self, user_id: str, api_key: str, api_base: str, model: str) -> dict:
        self.calls.append(("update_byok", (user_id, api_key, api_base, model), {}))
        return {"enabled": True, "model": model}

    def sync_project_session(self, **payload) -> dict:
        self.calls.append(("sync_project_session", (), payload))
        return payload

    def list_projects(self, user_id: str) -> dict:
        self.calls.append(("list_projects", (user_id,), {}))
        return {"projects": [{"id": "p1"}]}

    def get_team_profile(self, user_id: str) -> dict:
        self.calls.append(("get_team_profile", (user_id,), {}))
        return {"organization": {"id": "org-1"}}

    def rename_organization(self, user_id: str, organization_name: str) -> dict:
        self.calls.append(("rename_organization", (user_id, organization_name), {}))
        return {"organization": {"name": organization_name}}

    def add_team_member(self, user_id: str, **payload) -> dict:
        self.calls.append(("add_team_member", (user_id,), payload))
        return payload | {"user_id": user_id}

    def update_knowledge_scope(self, user_id: str, scope: str) -> dict:
        self.calls.append(("update_knowledge_scope", (user_id, scope), {}))
        return {"scope": scope}


def test_account_service_registers_trial_after_validation():
    store = FakeAccountStore()
    service = AccountService(store)

    user, token = service.register_trial(
        name="Trial User",
        email="trial@example.com",
        verification_code="123456",
        client_ip="127.0.0.1",
    )

    assert token == "tok"
    assert user["email"] == "trial@example.com"
    assert [call[0] for call in store.calls[:4]] == [
        "verify_code",
        "get_user_by_email",
        "check_ip_registration_limit",
        "register_trial",
    ]


def test_account_service_rejects_missing_bearer_token():
    service = AccountService(FakeAccountStore())

    try:
        service.get_current_user("")
    except ValueError as exc:
        assert str(exc) == "Missing Bearer token"
    else:
        raise AssertionError("expected missing bearer token to be rejected")
