from __future__ import annotations

from icore_agent.contexts.account.application.service import AccountService
from icore_agent.contexts.account.domain.account.plans import Plan
from icore_agent.contexts.account.domain.user import AuthenticatedUser, UserProfile


def _user(user_id: str = "u1", email: str = "trial@example.com") -> UserProfile:
    """Create a user profile for account service tests."""
    return UserProfile(
        public_id=user_id,
        email=email,
        name="Trial User",
        plan=Plan.TRIAL.value,
        plan_label=Plan.TRIAL.limits.label,
        roles=["owner"],
        byok={},
        usage={},
        created_at=1,
        updated_at=1,
    )


class FakeIdentityRepository:
    """Repository double for user identity and token lookup flows."""

    def __init__(self) -> None:
        """Create the fake identity repository."""
        self.calls: list[tuple[str, tuple, dict]] = []
        self.user_by_token = {"tok": _user()}
        self.registered_emails: set[str] = set()

    def get_user_by_token(self, token: str) -> UserProfile | None:
        """Record token lookup calls."""
        self.calls.append(("get_user_by_token", (token,), {}))
        return self.user_by_token.get(token)

    def get_user_by_id(self, user_id: str) -> UserProfile | None:
        """Record user-id lookup calls."""
        self.calls.append(("get_user_by_id", (user_id,), {}))
        if user_id == "u1":
            return _user()
        return None

    def get_user_by_email(self, email: str) -> UserProfile | None:
        """Record email lookup calls."""
        self.calls.append(("get_user_by_email", (email,), {}))
        normalized = email.strip().lower()
        if normalized in self.registered_emails:
            return _user(email=normalized)
        return None

    def email_exists(self, email: str) -> bool:
        """Record indexed email existence checks."""
        self.calls.append(("email_exists", (email,), {}))
        return email.strip().lower() in self.registered_emails

    def issue_token_for_user(self, user_id: str) -> str:
        """Record legacy token issuance calls."""
        self.calls.append(("issue_token_for_user", (user_id,), {}))
        return f"issued:{user_id}"


class FakeVerificationRepository:
    """Repository double for email verification flows."""

    def __init__(self) -> None:
        """Create the fake verification repository."""
        self.calls: list[tuple[str, tuple, dict]] = []

    def send_verification_code(self, email: str, client_ip: str) -> tuple[bool, str]:
        """Record verification delivery calls."""
        self.calls.append(("send_verification_code", (email, client_ip), {}))
        return True, f"sent:{email}:{client_ip}"

    def verify_code(self, email: str, code: str) -> bool:
        """Record verification validation calls."""
        self.calls.append(("verify_code", (email, code), {}))
        return code == "123456"


class FakeRegistrationRepository:
    """Repository double for registration-specific persistence."""

    def __init__(self) -> None:
        """Create the fake registration repository."""
        self.calls: list[tuple[str, tuple, dict]] = []

    def check_ip_registration_limit(self, client_ip: str) -> bool:
        """Record registration throttle checks."""
        self.calls.append(("check_ip_registration_limit", (client_ip,), {}))
        return True

    def register_trial(
        self,
        name: str,
        email: str,
        client_ip: str,
    ) -> tuple[UserProfile, str]:
        """Record trial registration calls."""
        self.calls.append(("register_trial", (name, email, client_ip), {}))
        return _user(email=email), "tok"


class FakeLeadRepository:
    """Repository double for lead capture persistence."""

    def __init__(self) -> None:
        """Create the fake lead repository."""
        self.calls: list[tuple[str, tuple, dict]] = []

    def create_lead(self, **payload) -> dict:
        """Record lead creation calls."""
        self.calls.append(("create_lead", (), payload))
        return payload | {"id": "lead-1"}


class FakeUsageService:
    """Service double for usage and quota related operations."""

    def __init__(self) -> None:
        """Create the fake usage service."""
        self.calls: list[tuple[str, tuple, dict]] = []

    def get_usage_summary(self, user_id: str) -> dict:
        """Record usage summary calls."""
        self.calls.append(("get_usage_summary", (user_id,), {}))
        return {"user_id": user_id}

    def get_admin_overview(self) -> dict:
        """Record admin overview calls."""
        self.calls.append(("get_admin_overview", (), {}))
        return {"users": {"total": 1}}

    def check_quota(self, user_id: str, resource: str) -> tuple[bool, str | None]:
        """Record quota check calls."""
        self.calls.append(("check_quota", (user_id, resource), {}))
        return True, None

    def consume_quota(self, user_id: str, resource: str) -> None:
        """Record quota consumption calls."""
        self.calls.append(("consume_quota", (user_id, resource), {}))


class FakeBillingSummaryRepository:
    """Repository double for plan summary and BYOK settings."""

    def __init__(self) -> None:
        """Create the fake billing summary repository."""
        self.calls: list[tuple[str, tuple, dict]] = []

    def get_plan_summary(self, user_id: str) -> dict:
        """Record plan summary calls."""
        self.calls.append(("get_plan_summary", (user_id,), {}))
        return {"user_id": user_id, "plan": "trial"}

    def update_byok(self, user_id: str, api_key: str, api_base: str, model: str) -> dict:
        """Record BYOK update calls."""
        self.calls.append(
            ("update_byok", (user_id, api_key, api_base, model), {})
        )
        return {"enabled": True, "model": model}


class FakeProjectRepository:
    """Repository double for project/session metadata."""

    def __init__(self) -> None:
        """Create the fake project repository."""
        self.calls: list[tuple[str, tuple, dict]] = []

    def sync_project_session(self, **payload) -> dict:
        """Record project sync calls."""
        self.calls.append(("sync_project_session", (), payload))
        return payload

    def list_projects(self, user_id: str) -> dict:
        """Record project listing calls."""
        self.calls.append(("list_projects", (user_id,), {}))
        return {"projects": [{"id": "p1"}]}


class FakeTeamRepository:
    """Repository double for team and organization management."""

    def __init__(self) -> None:
        """Create the fake team repository."""
        self.calls: list[tuple[str, tuple, dict]] = []

    def get_team_profile(self, user_id: str) -> dict:
        """Record team profile calls."""
        self.calls.append(("get_team_profile", (user_id,), {}))
        return {"organization": {"id": "org-1"}}

    def rename_organization(self, user_id: str, organization_name: str) -> dict:
        """Record organization rename calls."""
        self.calls.append(
            ("rename_organization", (user_id, organization_name), {})
        )
        return {"organization": {"name": organization_name}}

    def add_team_member(self, user_id: str, **payload) -> dict:
        """Record team member invite calls."""
        self.calls.append(("add_team_member", (user_id,), payload))
        return payload | {"user_id": user_id}

    def update_knowledge_scope(self, user_id: str, scope: str) -> dict:
        """Record knowledge scope update calls."""
        self.calls.append(("update_knowledge_scope", (user_id, scope), {}))
        return {"scope": scope}


def _account_service(
    *,
    identity: FakeIdentityRepository | None = None,
    verification: FakeVerificationRepository | None = None,
    registration: FakeRegistrationRepository | None = None,
    usage: FakeUsageService | None = None,
) -> AccountService:
    """Create an account service with test doubles."""
    return AccountService(
        identity_repository=identity or FakeIdentityRepository(),
        verification_repository=verification or FakeVerificationRepository(),
        registration_repository=registration or FakeRegistrationRepository(),
        lead_repository=FakeLeadRepository(),
        team_repository=FakeTeamRepository(),
        project_repository=FakeProjectRepository(),
        billing_summary_repository=FakeBillingSummaryRepository(),
        usage_service=usage or FakeUsageService(),
    )


def test_account_service_registers_trial_after_validation():
    """Verify registration validates code and issues a JWT."""
    identity = FakeIdentityRepository()
    verification = FakeVerificationRepository()
    registration = FakeRegistrationRepository()
    service = _account_service(
        identity=identity,
        verification=verification,
        registration=registration,
    )

    user, token = service.register_trial(
        name="Trial User",
        email="trial@example.com",
        verification_code="123456",
        client_ip="127.0.0.1",
    )

    assert token.count(".") == 2
    assert user.email == "trial@example.com"
    assert [call[0] for call in verification.calls] == ["verify_code"]
    assert [call[0] for call in identity.calls] == ["get_user_by_email"]
    assert [call[0] for call in registration.calls] == [
        "check_ip_registration_limit",
        "register_trial",
    ]

    resolved = service.get_current_user(f"Bearer {token}")

    assert resolved.public_id == "u1"
    assert resolved.roles == ["owner"]


def test_account_service_rejects_missing_bearer_token():
    """Verify missing bearer tokens are rejected before repository lookup."""
    service = _account_service()

    try:
        service.get_current_user("")
    except ValueError as exc:
        assert str(exc) == "Missing Bearer token"
    else:
        raise AssertionError("expected missing bearer token to be rejected")


def test_account_service_uses_usage_service_for_quota_checks():
    """Verify account workflows delegate quota decisions to UsageService."""
    usage = FakeUsageService()
    service = _account_service(usage=usage)

    allowed, reason = service.check_quota("u1", "messages")
    service.consume_quota("u1", "messages")

    assert (allowed, reason) == (True, None)
    assert [call[0] for call in usage.calls] == [
        "check_quota", "consume_quota"]


def test_admin_overview_requires_platform_admin_role():
    """Owner-only accounts must not access global admin metrics."""
    usage = FakeUsageService()
    service = _account_service(usage=usage)
    user = AuthenticatedUser(
        public_id="u1",
        email="trial@example.com",
        name="Trial User",
        roles=("owner",),
    )

    try:
        service.get_admin_overview(user)
    except PermissionError as exc:
        assert "admin" in str(exc).lower()
    else:
        raise AssertionError(
            "expected owner-only user to be denied admin overview")

    assert usage.calls == []


def test_admin_overview_allows_platform_admin_role():
    """Accounts with the admin role may access global admin metrics."""
    usage = FakeUsageService()
    service = _account_service(usage=usage)
    user = AuthenticatedUser(
        public_id="u1",
        email="ops@example.com",
        name="Ops User",
        roles=("owner", "admin"),
    )

    payload = service.get_admin_overview(user)

    assert payload["users"]["total"] == 1
    assert [call[0] for call in usage.calls] == ["get_admin_overview"]


def test_account_service_rejects_login_verification_for_unknown_email():
    """Login verification must fail fast when the email is not registered."""
    identity = FakeIdentityRepository()
    verification = FakeVerificationRepository()
    service = _account_service(identity=identity, verification=verification)

    try:
        service.send_verification_code(
            "missing@example.com",
            "127.0.0.1",
            purpose="login",
        )
    except LookupError as exc:
        assert "not registered" in str(exc)
    else:
        raise AssertionError("expected unknown login email to be rejected")

    assert [call[0] for call in identity.calls] == ["email_exists"]
    assert verification.calls == []


def test_account_service_sends_login_verification_for_registered_email():
    """Login verification should proceed only after a registered email check."""
    identity = FakeIdentityRepository()
    identity.registered_emails.add("trial@example.com")
    verification = FakeVerificationRepository()
    service = _account_service(identity=identity, verification=verification)

    success, message = service.send_verification_code(
        "trial@example.com",
        "127.0.0.1",
        purpose="login",
    )

    assert success is True
    assert message == "sent:trial@example.com:127.0.0.1"
    assert [call[0] for call in identity.calls] == ["email_exists"]
    assert [call[0]
            for call in verification.calls] == ["send_verification_code"]


def test_account_service_sends_register_verification_for_new_email():
    """Registration verification should proceed only when the email is available."""
    identity = FakeIdentityRepository()
    verification = FakeVerificationRepository()
    service = _account_service(identity=identity, verification=verification)

    success, message = service.send_verification_code(
        "new@example.com",
        "127.0.0.1",
        purpose="register",
    )

    assert success is True
    assert [call[0] for call in identity.calls] == ["email_exists"]
    assert [call[0]
            for call in verification.calls] == ["send_verification_code"]


def test_account_service_rejects_register_verification_for_existing_email():
    """Registration verification must fail fast when the email is already registered."""
    identity = FakeIdentityRepository()
    identity.registered_emails.add("trial@example.com")
    verification = FakeVerificationRepository()
    service = _account_service(identity=identity, verification=verification)

    try:
        service.send_verification_code(
            "trial@example.com",
            "127.0.0.1",
            purpose="register",
        )
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError(
            "expected registered email to be rejected during register verification")

    assert [call[0] for call in identity.calls] == ["email_exists"]
    assert verification.calls == []
