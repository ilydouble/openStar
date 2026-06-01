"""PostgreSQL-backed account repositories wired into the account service."""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Any

from icore_agent.application.workspace import WorkspaceMetadataService
from icore_agent.application.usage.policy import (
    admin_usage_overview,
    current_timestamp,
    default_usage,
    ensure_current_usage,
    next_quota_reset,

    plan_or_trial as plan_or_free,
    plan_usage_analytics,

)
from icore_agent.domain.account.plans import Plan
from icore_agent.domain.user import UserProfile

from ..sqlalchemy.sync_session import sync_session_scope
from .sqlalchemy_repository import SqlAlchemyUserRepository


def _default_byok() -> dict[str, Any]:
    """Return the default BYOK settings payload."""
    return {"enabled": False, "api_key": "", "api_base": "", "model": ""}


class PostgresIdentityRepository:
    """Load and issue account identities from PostgreSQL."""

    def __init__(self, store: Any, workspace: WorkspaceMetadataService) -> None:
        """Create an identity repository with legacy token and workspace stores."""
        self._store = store
        self._workspace = workspace

    def get_user_by_token(self, token: str) -> UserProfile | None:
        """Resolve a legacy bearer token to a persisted user profile."""
        user_id = self._store.get_user_id_for_token(token)
        if not user_id:
            return None
        return self.get_user_by_id(user_id)

    def get_user_by_id(self, user_id: str) -> UserProfile | None:
        """Load a user profile by public id."""
        with sync_session_scope() as session:
            repo = SqlAlchemyUserRepository(session)
            user = repo.get_by_public_id(user_id)
            if user is None:
                return None
            return self._workspace.ensure_organization_for_user(user)

    def get_user_by_email(self, email: str) -> UserProfile | None:
        """Load a user profile by email address."""
        with sync_session_scope() as session:
            repo = SqlAlchemyUserRepository(session)
            user = repo.get_by_email(email)
            if user is None:
                return None
            return self._workspace.ensure_organization_for_user(user)

    def email_exists(self, email: str) -> bool:
        """Return whether an email is registered using a single indexed lookup."""
        with sync_session_scope() as session:
            repo = SqlAlchemyUserRepository(session)
            return repo.email_exists(email)

    def issue_token_for_user(self, user_id: str) -> str:
        """Issue a legacy opaque token mapped to the user public id."""
        return self._store.issue_legacy_token(user_id)


class PostgresRegistrationRepository:
    """Register trial accounts in PostgreSQL and provision workspace metadata."""

    def __init__(self, store: Any, workspace: WorkspaceMetadataService) -> None:
        """Create a registration repository with control-plane and workspace stores."""
        self._store = store
        self._workspace = workspace

    def check_ip_registration_limit(self, client_ip: str) -> bool:
        """Delegate IP throttling to the JSON-backed control-plane store."""
        return self._store.check_ip_registration_limit(client_ip)

    def register_trial(
        self,
        name: str,
        email: str,
        client_ip: str,
    ) -> tuple[UserProfile, str]:
        """Create a trial account in PostgreSQL and persist org metadata."""
        normalized_email = email.strip().lower()
        with sync_session_scope() as session:
            repo = SqlAlchemyUserRepository(session)
            existing = repo.get_by_email(normalized_email)
            if existing is not None:
                token = self._store.issue_legacy_token(existing.public_id)
                return existing, token

            now = current_timestamp()
            # New accounts start on the TRIAL plan — a one-time gift of
            # 50 000 tokens (~30-50 AI conversations). When the trial quota
            # is exhausted the user is prompted to upgrade to a paid plan.
            plan = Plan.TRIAL
            user = repo.save(
                UserProfile(
                    public_id=str(uuid.uuid4()),
                    name=name.strip() or normalized_email.split("@")[0],
                    email=normalized_email,
                    plan=plan.value,
                    plan_label=plan.limits.label,
                    organization_id=f"org_{uuid.uuid4().hex[:12]}",
                    organization_name=f"{name.strip() or 'Trial'} Team",
                    roles=["owner"],
                    byok=_default_byok(),
                    usage=default_usage(),
                    created_at=now,
                    updated_at=now,
                )
            )

        self._workspace.create_organization_for_user(user)
        self._store.record_ip_registration(client_ip)
        self._store.append_event("trial_registered", user_id=user.public_id)
        token = self._store.issue_legacy_token(user.public_id)
        return user, token


class PostgresBillingSummaryRepository:
    """Read and update billing fields stored on the user profile."""

    def __init__(self, store: Any) -> None:
        """Create a billing summary repository with the control-plane store."""
        self._store = store

    def get_plan_summary(self, user_id: str) -> dict[str, Any]:
        """Return plan limits and usage counters for one user."""
        with sync_session_scope() as session:
            repo = SqlAlchemyUserRepository(session)
            user = repo.get_by_public_id(user_id)
            if user is None:
                raise KeyError(user_id)
            user, usage, should_save = ensure_current_usage(user)
            if should_save:
                user = repo.save(user)

                usage = {**default_usage(), **dict(user.usage or {})}
            plan = plan_or_free(user.plan)

            limits = plan.limits
            analytics = plan_usage_analytics(usage)
            return {
                "plan": plan.value,
                "label": limits.label,
                "limits": {
                    "tasks": limits.task_limit,
                    "attachments": limits.attachment_limit,
                },
                "usage": {
                    "tasks": usage.get("task_count", 0),
                    "tokens": usage.get("token_count", 0),
                    "attachments": usage.get("attachment_count", 0),
                    "estimated_cost": analytics["estimated_cost"],
                    "model_calls": analytics["model_calls"],
                    "active_models": analytics["active_models"],
                },
                "models_used": analytics["models_used"],
                "by_model": analytics["by_model"],
                "quota_period": {
                    "start": usage.get("quota_period_start", 0),
                    "next_reset": next_quota_reset(),
                },
                "byok": dict(user.byok or _default_byok()),
            }

    def update_byok(
        self,
        user_id: str,
        api_key: str,
        api_base: str,
        model: str,
    ) -> dict[str, Any]:
        """Persist BYOK settings for one user."""
        byok = {
            "enabled": bool(api_key),
            "api_key": api_key.strip(),
            "api_base": api_base.strip(),
            "model": model.strip(),
        }
        with sync_session_scope() as session:
            repo = SqlAlchemyUserRepository(session)
            user = repo.get_by_public_id(user_id)
            if user is None:
                raise KeyError(user_id)
            repo.save(replace(user, byok=byok, updated_at=current_timestamp()))
        self._store.append_event("byok_updated", user_id=user_id)
        return byok


class PostgresBillingRepository:
    """Apply billing plan changes to PostgreSQL user profiles."""

    def __init__(self, store: Any) -> None:
        """Create a billing repository with the control-plane store."""
        self._store = store

    def update_user_plan(self, **payload: Any) -> dict[str, Any]:
        """Update one user's billing plan."""
        user_id = str(payload["user_id"])
        plan = plan_or_trial(str(payload["new_plan"]))
        byok = {
            "enabled": bool(payload.get("byok_enabled")),
            "api_key": str(payload.get("byok_api_key") or "").strip(),
            "api_base": str(payload.get("byok_api_base") or "").strip(),
            "model": str(payload.get("byok_model") or "").strip(),
        }
        with sync_session_scope() as session:
            repo = SqlAlchemyUserRepository(session)
            user = repo.get_by_public_id(user_id)
            if user is None:
                raise KeyError(user_id)
            old_plan = user.plan
            saved = repo.save(
                replace(
                    user,
                    plan=plan.value,
                    plan_label=plan.limits.label,
                    byok=byok,
                    updated_at=current_timestamp(),
                )
            )
        self._store.append_event(
            "plan_updated",
            user_id=user_id,
            old_plan=old_plan,
            new_plan=plan.value,
        )
        return {
            "id": saved.public_id,
            "plan": saved.plan,
            "plan_label": saved.plan_label,
        }


class PostgresUsageRepository:
    """Usage persistence store backed by PostgreSQL users and JSON usage events."""

    def __init__(self, store: Any) -> None:
        """Create a usage store with the control-plane event store."""
        self._store = store

    def get_user_by_id(self, user_id: str) -> UserProfile | None:
        """Load one user profile by public id."""
        with sync_session_scope() as session:
            repo = SqlAlchemyUserRepository(session)
            return repo.get_by_public_id(user_id)

    def save_user(self, user: UserProfile) -> UserProfile:
        """Persist one changed user profile."""
        with sync_session_scope() as session:
            repo = SqlAlchemyUserRepository(session)
            return repo.save(user)

    def list_users(self) -> list[UserProfile]:
        """Return all user profiles for admin usage reporting."""
        with sync_session_scope() as session:
            repo = SqlAlchemyUserRepository(session)
            return repo.list_all()

    def record_usage_event(self, **payload: Any) -> None:
        """Persist one LLM usage event in the control-plane event store."""
        self._store.record_usage_event(**payload)

    def usage_summary(self, user_id: str) -> dict[str, Any]:
        """Return token usage events aggregated from the JSON store."""
        return self._store.usage_summary(user_id)

    def admin_overview(self, users: list[UserProfile]) -> dict[str, Any]:
        """Return admin metrics from PostgreSQL usage plus JSON funnel metadata."""
        funnel = self._store.account_funnel_meta()
        return admin_usage_overview(
            users,
            new_trials_7d=int(funnel.get("new_trials_7d", 0) or 0),
            leads=funnel.get("leads"),
        )


class PostgresTeamRepository:
    """Team operations backed by PostgreSQL organization metadata."""

    def __init__(self, workspace: WorkspaceMetadataService) -> None:
        """Create a team repository with the workspace metadata service."""
        self._workspace = workspace

    def get_team_profile(self, user_id: str) -> dict[str, Any]:
        """Return the organization profile for the current user."""
        return self._workspace.get_team_profile(user_id)

    def rename_organization(self, user_id: str, organization_name: str) -> dict[str, Any]:
        """Rename the user's organization."""
        return self._workspace.rename_organization(user_id, organization_name)

    def add_team_member(self, user_id: str, **payload: Any) -> dict[str, Any]:
        """Add a team member to the organization roster."""
        return self._workspace.add_team_member(user_id, **payload)

    def update_knowledge_scope(self, user_id: str, scope: str) -> dict[str, Any]:
        """Update the organization knowledge scope for the current user."""
        return self._workspace.update_knowledge_scope(user_id, scope)


class PostgresProjectRepository:
    """Project metadata stored in PostgreSQL with Redis caching."""

    def __init__(self, workspace: WorkspaceMetadataService) -> None:
        """Create a project repository with the workspace metadata service."""
        self._workspace = workspace

    def sync_project_session(self, **payload: Any) -> dict[str, Any]:
        """Sync one project/session record for a user."""
        return self._workspace.sync_project_session(**payload)

    def list_projects(self, user_id: str) -> dict[str, Any]:
        """List projects visible to the user's organization."""
        return self._workspace.list_projects(user_id)
