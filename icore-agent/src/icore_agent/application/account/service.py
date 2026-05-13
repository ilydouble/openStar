"""Application service for account, quota, team, and project workflows."""

from __future__ import annotations

from typing import Any, Protocol


class AccountStore(Protocol):
    """Persistence contract used by the account application service."""

    def get_user_by_token(self, token: str) -> dict[str, Any] | None: ...
    def send_verification_code(self, email: str, client_ip: str) -> tuple[bool, str]: ...
    def verify_code(self, email: str, code: str) -> bool: ...
    def get_user_by_email(self, email: str) -> dict[str, Any] | None: ...
    def issue_token_for_user(self, user_id: str) -> str: ...
    def check_ip_registration_limit(self, client_ip: str) -> bool: ...
    def register_trial(self, name: str, email: str, client_ip: str) -> tuple[dict[str, Any], str]: ...
    def create_lead(self, **payload: Any) -> dict[str, Any]: ...
    def usage_summary(self, user_id: str) -> dict[str, Any]: ...
    def admin_overview(self) -> dict[str, Any]: ...
    def get_plan_summary(self, user_id: str) -> dict[str, Any]: ...
    def update_byok(self, user_id: str, api_key: str, api_base: str, model: str) -> dict[str, Any]: ...
    def sync_project_session(self, **payload: Any) -> dict[str, Any]: ...
    def list_projects(self, user_id: str) -> dict[str, Any]: ...
    def get_team_profile(self, user_id: str) -> dict[str, Any]: ...
    def rename_organization(self, user_id: str, organization_name: str) -> dict[str, Any]: ...
    def add_team_member(self, user_id: str, **payload: Any) -> dict[str, Any]: ...
    def update_knowledge_scope(self, user_id: str, scope: str) -> dict[str, Any]: ...
    def check_quota(self, user_id: str, resource: str) -> tuple[bool, str]: ...
    def consume_quota(self, user_id: str, resource: str) -> None: ...


class AccountService:
    """Coordinate account workflows while hiding the storage implementation."""

    def __init__(self, store: AccountStore) -> None:
        """Create an account service bound to one persistence adapter."""
        self._store = store

    def get_current_user(self, authorization: str) -> dict[str, Any]:
        """Resolve the bearer token into the current user payload."""
        if not authorization.startswith("Bearer "):
            raise ValueError("Missing Bearer token")
        token = authorization[7:].strip()
        user = self._store.get_user_by_token(token)
        if user is None:
            raise LookupError("Invalid or expired token")
        return user

    def send_verification_code(self, email: str, client_ip: str) -> tuple[bool, str]:
        """Dispatch a verification code to the given email."""
        return self._store.send_verification_code(email, client_ip)

    def login_with_email_code(self, email: str, verification_code: str) -> tuple[dict[str, Any], str]:
        """Validate a one-time code and issue a fresh access token."""
        if not self._store.verify_code(email, verification_code):
            raise ValueError("验证码错误或已过期")
        user = self._store.get_user_by_email(email)
        if not user:
            raise LookupError("该邮箱尚未注册，请先注册试用账号")
        token = self._store.issue_token_for_user(user["id"])
        return user, token

    def register_trial(
        self,
        *,
        name: str,
        email: str,
        verification_code: str,
        client_ip: str,
    ) -> tuple[dict[str, Any], str]:
        """Register a new trial user after code and IP checks pass."""
        if not self._store.verify_code(email, verification_code):
            raise ValueError("验证码错误或已过期")
        existing_user = self._store.get_user_by_email(email)
        if existing_user:
            raise ValueError("该邮箱已注册，请使用「邮箱登录」功能")
        if not self._store.check_ip_registration_limit(client_ip):
            raise PermissionError("同一 IP 24 小时内只能注册 1 次账号")
        return self._store.register_trial(name, email, client_ip)

    def capture_lead(self, **payload: Any) -> dict[str, Any]:
        """Create a lead capture record for the marketing funnel."""
        return self._store.create_lead(**payload)

    def get_usage_summary(self, user_id: str) -> dict[str, Any]:
        """Load the usage summary for one user."""
        return self._store.usage_summary(user_id)

    def get_admin_overview(self, user: dict[str, Any]) -> dict[str, Any]:
        """Return admin-only usage metrics after a role check."""
        roles = user.get("roles") or []
        if "owner" not in roles and "admin" not in roles:
            raise PermissionError(
                "Admin access required. Only users with 'owner' or 'admin' role can access this endpoint."
            )
        return self._store.admin_overview()

    def get_plan(self, user_id: str) -> dict[str, Any]:
        """Return the billing plan summary for a user."""
        return self._store.get_plan_summary(user_id)

    def update_byok(self, user_id: str, api_key: str, api_base: str, model: str) -> dict[str, Any]:
        """Persist BYOK model credentials for a user."""
        return self._store.update_byok(user_id, api_key, api_base, model)

    def sync_project(self, **payload: Any) -> dict[str, Any]:
        """Persist project/session metadata for the workspace UI."""
        return self._store.sync_project_session(**payload)

    def list_projects(self, user_id: str) -> dict[str, Any]:
        """List project summaries owned by a user."""
        return self._store.list_projects(user_id)

    def get_team(self, user_id: str) -> dict[str, Any]:
        """Load the current team profile."""
        return self._store.get_team_profile(user_id)

    def rename_team(self, user_id: str, organization_name: str) -> dict[str, Any]:
        """Rename the current organization."""
        return self._store.rename_organization(user_id, organization_name)

    def add_team_member(self, user_id: str, **payload: Any) -> dict[str, Any]:
        """Add a team member to the current organization."""
        return self._store.add_team_member(user_id, **payload)

    def update_team_knowledge_scope(self, user_id: str, scope: str) -> dict[str, Any]:
        """Update whether knowledge sharing is private or organization-wide."""
        return self._store.update_knowledge_scope(user_id, scope)

    def check_quota(self, user_id: str, resource: str) -> tuple[bool, str]:
        """Read a quota decision without consuming the quota yet."""
        return self._store.check_quota(user_id, resource)

    def consume_quota(self, user_id: str, resource: str) -> None:
        """Consume one quota unit after a request is accepted."""
        self._store.consume_quota(user_id, resource)
