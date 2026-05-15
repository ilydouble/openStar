"""Application service for account, quota, team, and project workflows."""

from __future__ import annotations

from typing import Any

from ...config import settings
from ...lib.auth.jwt import JWTValidationError, sign_access_token, verify_access_token
from .contracts import (
    BillingSummaryRepository,
    IdentityRepository,
    LeadRepository,
    ProjectRepository,
    RegistrationRepository,
    TeamRepository,
    UsageRepository,
    VerificationRepository,
)


class AccountService:
    """Coordinate account workflows while hiding the storage implementation."""

    def __init__(
        self,
        *,
        identity_repository: IdentityRepository,
        verification_repository: VerificationRepository,
        registration_repository: RegistrationRepository,
        lead_repository: LeadRepository,
        team_repository: TeamRepository,
        project_repository: ProjectRepository,
        billing_summary_repository: BillingSummaryRepository,
        usage_repository: UsageRepository,
    ) -> None:
        """Create an account service from narrow repository contracts."""
        self._identity_repository = identity_repository
        self._verification_repository = verification_repository
        self._registration_repository = registration_repository
        self._lead_repository = lead_repository
        self._team_repository = team_repository
        self._project_repository = project_repository
        self._billing_summary_repository = billing_summary_repository
        self._usage_repository = usage_repository

    def get_current_user(self, authorization: str) -> dict[str, Any]:
        """Resolve the bearer JWT into the current user payload."""
        if not authorization.startswith("Bearer "):
            raise ValueError("Missing Bearer token")
        token = authorization[7:].strip()
        try:
            claims = verify_access_token(
                token,
                secret=settings.jwt_secret,
                issuer=settings.jwt_issuer,
                audience=settings.jwt_audience,
            )
        except JWTValidationError as exc:
            raise LookupError("Invalid or expired token") from exc

        user = self._identity_repository.get_user_by_id(claims["sub"])
        if user is None:
            raise LookupError("Invalid or expired token")
        return user

    def send_verification_code(self, email: str, client_ip: str) -> tuple[bool, str]:
        """Dispatch a verification code to the given email."""
        return self._verification_repository.send_verification_code(email, client_ip)

    def login_with_email_code(self, email: str, verification_code: str) -> tuple[dict[str, Any], str]:
        """Validate a one-time code and issue a fresh access token."""
        if not self._verification_repository.verify_code(email, verification_code):
            raise ValueError("验证码错误或已过期")
        user = self._identity_repository.get_user_by_email(email)
        if not user:
            raise LookupError("该邮箱尚未注册，请先注册试用账号")
        return user, self._issue_access_token(user)

    def register_trial(
        self,
        *,
        name: str,
        email: str,
        verification_code: str,
        client_ip: str,
    ) -> tuple[dict[str, Any], str]:
        """Register a new trial user after code and IP checks pass."""
        if not self._verification_repository.verify_code(email, verification_code):
            raise ValueError("验证码错误或已过期")
        existing_user = self._identity_repository.get_user_by_email(email)
        if existing_user:
            raise ValueError("该邮箱已注册，请使用「邮箱登录」功能")
        if not self._registration_repository.check_ip_registration_limit(client_ip):
            raise PermissionError("同一 IP 24 小时内只能注册 1 次账号")
        user, _legacy_token = self._registration_repository.register_trial(
            name, email, client_ip)
        return user, self._issue_access_token(user)

    def _issue_access_token(self, user: dict[str, Any]) -> str:
        """Create the JWT access token consumed by the Go gateway and backend."""
        return sign_access_token(
            user=user,
            secret=settings.jwt_secret,
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            ttl_seconds=settings.jwt_ttl_seconds,
        )

    def capture_lead(self, **payload: Any) -> dict[str, Any]:
        """Create a lead capture record for the marketing funnel."""
        return self._lead_repository.create_lead(**payload)

    def get_usage_summary(self, user_id: str) -> dict[str, Any]:
        """Load the usage summary for one user."""
        return self._usage_repository.usage_summary(user_id)

    def get_admin_overview(self, user: dict[str, Any]) -> dict[str, Any]:
        """Return admin-only usage metrics after a role check."""
        roles = user.get("roles") or []
        if "owner" not in roles and "admin" not in roles:
            raise PermissionError(
                "Admin access required. Only users with 'owner' or 'admin' role can access this endpoint."
            )
        return self._usage_repository.admin_overview()

    def get_plan(self, user_id: str) -> dict[str, Any]:
        """Return the billing plan summary for a user."""
        return self._billing_summary_repository.get_plan_summary(user_id)

    def update_byok(self, user_id: str, api_key: str, api_base: str, model: str) -> dict[str, Any]:
        """Persist BYOK model credentials for a user."""
        return self._billing_summary_repository.update_byok(user_id, api_key, api_base, model)

    def sync_project(self, **payload: Any) -> dict[str, Any]:
        """Persist project/session metadata for the workspace UI."""
        return self._project_repository.sync_project_session(**payload)

    def list_projects(self, user_id: str) -> dict[str, Any]:
        """List project summaries owned by a user."""
        return self._project_repository.list_projects(user_id)

    def get_team(self, user_id: str) -> dict[str, Any]:
        """Load the current team profile."""
        return self._team_repository.get_team_profile(user_id)

    def rename_team(self, user_id: str, organization_name: str) -> dict[str, Any]:
        """Rename the current organization."""
        return self._team_repository.rename_organization(user_id, organization_name)

    def add_team_member(self, user_id: str, **payload: Any) -> dict[str, Any]:
        """Add a team member to the current organization."""
        return self._team_repository.add_team_member(user_id, **payload)

    def update_team_knowledge_scope(self, user_id: str, scope: str) -> dict[str, Any]:
        """Update whether knowledge sharing is private or organization-wide."""
        return self._team_repository.update_knowledge_scope(user_id, scope)

    def check_quota(self, user_id: str, resource: str) -> tuple[bool, str | None]:
        """Read a quota decision without consuming the quota yet."""
        return self._usage_repository.check_quota(user_id, resource)

    def consume_quota(self, user_id: str, resource: str) -> None:
        """Consume one quota unit after a request is accepted."""
        self._usage_repository.consume_quota(user_id, resource)
