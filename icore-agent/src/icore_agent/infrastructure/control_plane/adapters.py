"""Infrastructure adapters that wrap the JSON-backed control-plane store."""

from __future__ import annotations

from typing import Any


class ControlPlaneIdentityRepository:
    """Adapter exposing only identity and token lookup operations."""

    def __init__(self, store: Any) -> None:
        """Create an identity repository adapter bound to one control-plane store."""
        self._store = store

    def get_user_by_token(self, token: str) -> dict[str, Any] | None:
        """Load a user by bearer token."""
        return self._store.get_user_by_token(token)

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        """Load a user by stable user id."""
        return self._store.get_user_by_id(user_id)

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        """Load a user by email address."""
        return self._store.get_user_by_email(email)

    def issue_token_for_user(self, user_id: str) -> str:
        """Issue a new access token for an existing user."""
        return self._store.issue_token_for_user(user_id)


class ControlPlaneVerificationRepository:
    """Adapter exposing verification delivery and validation operations."""

    def __init__(self, store: Any) -> None:
        """Create a verification repository adapter bound to one control-plane store."""
        self._store = store

    def send_verification_code(self, email: str, client_ip: str) -> tuple[bool, str]:
        """Request an email verification code."""
        return self._store.send_verification_code(email, client_ip)

    def verify_code(self, email: str, code: str) -> bool:
        """Validate an email verification code."""
        return self._store.verify_code(email, code)


class ControlPlaneRegistrationRepository:
    """Adapter exposing registration-specific persistence operations."""

    def __init__(self, store: Any) -> None:
        """Create a registration repository adapter bound to one control-plane store."""
        self._store = store

    def check_ip_registration_limit(self, client_ip: str) -> bool:
        """Check whether the IP-based registration limit still allows one more signup."""
        return self._store.check_ip_registration_limit(client_ip)

    def register_trial(self, name: str, email: str, client_ip: str) -> tuple[dict[str, Any], str]:
        """Register a new trial/free account."""
        return self._store.register_trial(name, email, client_ip)


class ControlPlaneLeadRepository:
    """Adapter exposing lead capture operations."""

    def __init__(self, store: Any) -> None:
        """Create a lead repository adapter bound to one control-plane store."""
        self._store = store

    def create_lead(self, **payload: Any) -> dict[str, Any]:
        """Store a lead capture record."""
        return self._store.create_lead(**payload)


class ControlPlaneTeamRepository:
    """Adapter exposing organization and team management operations."""

    def __init__(self, store: Any) -> None:
        """Create a team repository adapter bound to one control-plane store."""
        self._store = store

    def get_team_profile(self, user_id: str) -> dict[str, Any]:
        """Return the organization profile for one user."""
        return self._store.get_team_profile(user_id)

    def rename_organization(self, user_id: str, organization_name: str) -> dict[str, Any]:
        """Rename the current organization."""
        return self._store.rename_organization(user_id, organization_name)

    def add_team_member(self, user_id: str, **payload: Any) -> dict[str, Any]:
        """Add a team member to the organization."""
        return self._store.add_team_member(user_id, **payload)

    def update_knowledge_scope(self, user_id: str, scope: str) -> dict[str, Any]:
        """Persist the team's knowledge sharing scope."""
        return self._store.update_knowledge_scope(user_id, scope)


class ControlPlaneProjectRepository:
    """Adapter exposing project and session metadata operations."""

    def __init__(self, store: Any) -> None:
        """Create a project repository adapter bound to one control-plane store."""
        self._store = store

    def sync_project_session(self, **payload: Any) -> dict[str, Any]:
        """Sync project and session metadata."""
        return self._store.sync_project_session(**payload)

    def list_projects(self, user_id: str) -> dict[str, Any]:
        """List projects owned by a user."""
        return self._store.list_projects(user_id)


class ControlPlaneBillingSummaryRepository:
    """Adapter exposing plan summary and BYOK operations."""

    def __init__(self, store: Any) -> None:
        """Create a billing summary repository adapter bound to one control-plane store."""
        self._store = store

    def get_plan_summary(self, user_id: str) -> dict[str, Any]:
        """Return the current billing plan summary for one user."""
        return self._store.get_plan_summary(user_id)

    def update_byok(self, user_id: str, api_key: str, api_base: str, model: str) -> dict[str, Any]:
        """Persist BYOK configuration for one user."""
        return self._store.update_byok(user_id, api_key, api_base, model)


class ControlPlaneBillingRepository:
    """Adapter exposing billing-related store operations."""

    def __init__(self, store: Any) -> None:
        """Create a billing repository adapter bound to one control-plane store."""
        self._store = store

    def update_user_plan(self, **payload: Any) -> dict[str, Any]:
        """Update the current billing plan through the control-plane store."""
        return self._store.update_user_plan(**payload)


class ControlPlaneUsageRepository:
    """Adapter exposing usage, quota, and admin reporting operations."""

    def __init__(self, store: Any) -> None:
        """Create a usage repository adapter bound to one control-plane store."""
        self._store = store

    def check_quota(self, user_id: str, resource: str) -> tuple[bool, str | None]:
        """Return whether the given resource quota allows one more action."""
        return self._store.check_quota(user_id, resource)

    def consume_quota(self, user_id: str, resource: str) -> None:
        """Consume one unit from the given resource quota."""
        self._store.consume_quota(user_id, resource)

    def usage_summary(self, user_id: str) -> dict[str, Any]:
        """Return the current usage summary for one user."""
        return self._store.usage_summary(user_id)

    def admin_overview(self) -> dict[str, Any]:
        """Return global admin metrics."""
        return self._store.admin_overview()

    def record_usage_event(self, **payload: Any) -> None:
        """Persist one usage event."""
        self._store.record_usage_event(**payload)
