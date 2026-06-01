"""Infrastructure adapters that wrap the JSON-backed control-plane store."""

from __future__ import annotations

from typing import Any

from icore_agent.application.usage import UsageService
from icore_agent.application.workspace import WorkspaceMetadataService
from icore_agent.domain.user import UserProfile

from ..persistence.users.postgres_repositories import (
    PostgresBillingRepository,
    PostgresBillingSummaryRepository,
    PostgresIdentityRepository,
    PostgresProjectRepository,
    PostgresRegistrationRepository,
    PostgresTeamRepository,
    PostgresUsageRepository,
)


def _workspace_service() -> WorkspaceMetadataService:
    """Return a stateless workspace metadata service for adapter wiring."""
    return WorkspaceMetadataService()


class ControlPlaneIdentityRepository:
    """Adapter exposing identity lookup backed by PostgreSQL user profiles."""

    def __init__(self, store: Any) -> None:
        """Create an identity repository adapter bound to one control-plane store."""
        self._postgres = PostgresIdentityRepository(store, _workspace_service())

    def get_user_by_token(self, token: str) -> UserProfile | None:
        """Load a user by bearer token."""
        return self._postgres.get_user_by_token(token)

    def get_user_by_id(self, user_id: str) -> UserProfile | None:
        """Load a user by stable user id."""
        return self._postgres.get_user_by_id(user_id)

    def get_user_by_email(self, email: str) -> UserProfile | None:
        """Load a user by email address."""
        return self._postgres.get_user_by_email(email)

    def email_exists(self, email: str) -> bool:
        """Return whether an email is registered."""
        return self._postgres.email_exists(email)

    def issue_token_for_user(self, user_id: str) -> str:
        """Issue a new access token for an existing user."""
        return self._postgres.issue_token_for_user(user_id)


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
    """Adapter exposing registration backed by PostgreSQL user profiles."""

    def __init__(self, store: Any) -> None:
        """Create a registration repository adapter bound to one control-plane store."""
        self._postgres = PostgresRegistrationRepository(store, _workspace_service())

    def check_ip_registration_limit(self, client_ip: str) -> bool:
        """Check whether the IP-based registration limit still allows one more signup."""
        return self._postgres.check_ip_registration_limit(client_ip)

    def register_trial(self, name: str, email: str, client_ip: str) -> tuple[UserProfile, str]:
        """Register a new trial/free account."""
        return self._postgres.register_trial(name, email, client_ip)


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
        self._postgres = PostgresTeamRepository(_workspace_service())

    def get_team_profile(self, user_id: str) -> dict[str, Any]:
        """Return the organization profile for one user."""
        return self._postgres.get_team_profile(user_id)

    def rename_organization(self, user_id: str, organization_name: str) -> dict[str, Any]:
        """Rename the current organization."""
        return self._postgres.rename_organization(user_id, organization_name)

    def add_team_member(self, user_id: str, **payload: Any) -> dict[str, Any]:
        """Add a team member to the organization."""
        return self._postgres.add_team_member(user_id, **payload)

    def update_knowledge_scope(self, user_id: str, scope: str) -> dict[str, Any]:
        """Persist the team's knowledge sharing scope."""
        return self._postgres.update_knowledge_scope(user_id, scope)


class ControlPlaneProjectRepository:
    """Adapter exposing project and session metadata operations."""

    def __init__(self, store: Any) -> None:
        """Create a project repository adapter bound to one control-plane store."""
        self._postgres = PostgresProjectRepository(_workspace_service())

    def sync_project_session(self, **payload: Any) -> dict[str, Any]:
        """Sync project and session metadata."""
        return self._postgres.sync_project_session(**payload)

    def list_projects(self, user_id: str) -> dict[str, Any]:
        """List projects owned by a user."""
        return self._postgres.list_projects(user_id)


class ControlPlaneBillingSummaryRepository:
    """Adapter exposing plan summary and BYOK operations."""

    def __init__(self, store: Any) -> None:
        """Create a billing summary repository adapter bound to one control-plane store."""
        self._postgres = PostgresBillingSummaryRepository(store)

    def get_plan_summary(self, user_id: str) -> dict[str, Any]:
        """Return the current billing plan summary for one user."""
        return self._postgres.get_plan_summary(user_id)

    def update_byok(self, user_id: str, api_key: str, api_base: str, model: str) -> dict[str, Any]:
        """Persist BYOK configuration for one user."""
        return self._postgres.update_byok(user_id, api_key, api_base, model)


class ControlPlaneBillingRepository:
    """Adapter exposing billing-related store operations."""

    def __init__(self, store: Any) -> None:
        """Create a billing repository adapter bound to one control-plane store."""
        self._postgres = PostgresBillingRepository(store)

    def update_user_plan(self, **payload: Any) -> dict[str, Any]:
        """Update the current billing plan through the control-plane store."""
        return self._postgres.update_user_plan(**payload)


class ControlPlaneUsageRepository:
    """Adapter exposing usage, quota, and admin reporting operations."""

    def __init__(self, store: Any) -> None:
        """Create a usage repository adapter bound to one control-plane store."""
        self._postgres = PostgresUsageRepository(store)
        self._service = UsageService(self._postgres)

    def check_quota(self, user_id: str, resource: str) -> tuple[bool, str | None]:
        """Return whether the given resource quota allows one more action."""
        return self._service.check_quota(user_id, resource)

    def consume_quota(self, user_id: str, resource: str) -> None:
        """Consume one unit from the given resource quota."""
        self._service.consume_quota(user_id, resource)

    def usage_summary(self, user_id: str) -> dict[str, Any]:
        """Return the current usage summary for one user."""
        return self._service.get_usage_summary(user_id)

    def admin_overview(self) -> dict[str, Any]:
        """Return global admin metrics."""
        return self._service.get_admin_overview()

    def record_usage_event(self, **payload: Any) -> None:
        """Persist one usage event."""
        self._postgres.record_usage_event(**payload)
