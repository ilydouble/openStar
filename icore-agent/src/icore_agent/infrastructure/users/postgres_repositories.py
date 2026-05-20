"""PostgreSQL-backed account repositories wired into the account service."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from typing import Any

from ...control_plane.constants import PLAN_LIMITS
from ...database.sync_session import sync_session_scope
from ...users.repository import UserRepository


class PostgresIdentityRepository:
    """Load and issue account identities from PostgreSQL."""

    def __init__(self, store: Any) -> None:
        self._store = store

    def get_user_by_token(self, token: str) -> dict[str, Any] | None:
        """Resolve a legacy bearer token to a persisted user profile."""
        user_id = self._store.get_user_id_for_token(token)
        if not user_id:
            return None
        return self.get_user_by_id(user_id)

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        """Load a user profile by public id."""
        with sync_session_scope() as session:
            repo = UserRepository(session)
            user = repo.get_by_public_id(user_id)
            if user is None:
                return None
            self._store.ensure_organization_for_user(repo.to_api_dict(user))
            return repo.to_api_dict(user)

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        """Load a user profile by email address."""
        with sync_session_scope() as session:
            repo = UserRepository(session)
            user = repo.get_by_email(email)
            if user is None:
                return None
            self._store.ensure_organization_for_user(repo.to_api_dict(user))
            return repo.to_api_dict(user)

    def issue_token_for_user(self, user_id: str) -> str:
        """Issue a legacy opaque token mapped to the user public id."""
        return self._store.issue_legacy_token(user_id)


class PostgresRegistrationRepository:
    """Register trial accounts in PostgreSQL while keeping org metadata in JSON."""

    def __init__(self, store: Any) -> None:
        self._store = store

    def check_ip_registration_limit(self, client_ip: str) -> bool:
        """Delegate IP throttling to the JSON-backed control-plane store."""
        return self._store.check_ip_registration_limit(client_ip)

    def register_trial(self, name: str, email: str, client_ip: str) -> tuple[dict[str, Any], str]:
        """Create a trial account in PostgreSQL and persist org metadata."""
        with sync_session_scope() as session:
            repo = UserRepository(session)
            existing = repo.get_by_email(email)
            if existing is not None:
                user_dict = repo.to_api_dict(existing)
                token = self._store.issue_legacy_token(user_dict["id"])
                return user_dict, token

            org_id = f"org_{uuid.uuid4().hex[:12]}"
            org_name = f"{name.strip() or 'Free'} Team"
            user = repo.create_trial_user(
                name=name,
                email=email,
                organization_id=org_id,
                organization_name=org_name,
            )
            user_dict = repo.to_api_dict(user)

        self._store.create_organization_for_user(user_dict)
        self._store.record_ip_registration(client_ip)
        self._store.append_event("trial_registered", user_id=user_dict["id"])
        token = self._store.issue_legacy_token(user_dict["id"])
        return user_dict, token


class PostgresBillingSummaryRepository:
    """Read and update billing fields stored on the user profile."""

    def __init__(self, store: Any) -> None:
        self._store = store

    def get_plan_summary(self, user_id: str) -> dict[str, Any]:
        """Return plan limits and usage counters for one user."""
        with sync_session_scope() as session:
            repo = UserRepository(session)
            user = repo.get_by_public_id(user_id)
            if user is None:
                raise KeyError(user_id)
            usage = repo.ensure_usage(user)
            limits = PLAN_LIMITS[user.plan]
            now = datetime.now(UTC)
            if now.month == 12:
                next_reset = datetime(now.year + 1, 1, 1, 0, 0, 0, tzinfo=UTC)
            else:
                next_reset = datetime(now.year, now.month + 1, 1, 0, 0, 0, tzinfo=UTC)
            return {
                "plan": user.plan,
                "label": limits["label"],
                "limits": {
                    "messages": limits["message_limit"],
                    "tokens": limits["token_limit"],
                    "images": limits["image_limit"],
                    "attachments": limits["attachment_limit"],
                },
                "usage": {
                    "messages": usage["message_count"],
                    "tokens": usage["token_count"],
                    "images": usage["image_count"],
                    "attachments": usage["attachment_count"],
                },
                "quota_period": {
                    "start": usage.get("quota_period_start", 0),
                    "next_reset": int(next_reset.timestamp()),
                },
                "byok": dict(
                    user.byok
                    or {"enabled": False, "api_key": "", "api_base": "", "model": ""}
                ),
            }

    def update_byok(self, user_id: str, api_key: str, api_base: str, model: str) -> dict[str, Any]:
        """Persist BYOK settings for one user."""
        with sync_session_scope() as session:
            repo = UserRepository(session)
            user = repo.get_by_public_id(user_id)
            if user is None:
                raise KeyError(user_id)
            byok = repo.update_byok(
                user,
                api_key=api_key,
                api_base=api_base,
                model=model,
            )
        self._store.append_event("byok_updated", user_id=user_id)
        return byok


class PostgresBillingRepository:
    """Apply billing plan changes to PostgreSQL user profiles."""

    def __init__(self, store: Any) -> None:
        self._store = store

    def update_user_plan(self, **payload: Any) -> dict[str, Any]:
        """Update one user's billing plan."""
        user_id = str(payload["user_id"])
        new_plan = str(payload["new_plan"])
        with sync_session_scope() as session:
            repo = UserRepository(session)
            user = repo.get_by_public_id(user_id)
            if user is None:
                raise KeyError(user_id)
            old_plan = user.plan
            user = repo.update_plan(
                user,
                new_plan=new_plan,
                byok_enabled=bool(payload.get("byok_enabled")),
                byok_api_key=str(payload.get("byok_api_key") or ""),
                byok_api_base=str(payload.get("byok_api_base") or ""),
                byok_model=str(payload.get("byok_model") or ""),
            )
            user_dict = repo.to_api_dict(user)
        self._store.append_event(
            "plan_updated",
            user_id=user_id,
            old_plan=old_plan,
            new_plan=new_plan,
        )
        return user_dict


class PostgresUsageRepository:
    """Quota and admin usage reporting backed by PostgreSQL user profiles."""

    def __init__(self, store: Any) -> None:
        self._store = store

    def check_quota(self, user_id: str, resource: str) -> tuple[bool, str | None]:
        """Return whether one more unit of quota can be consumed."""
        with sync_session_scope() as session:
            repo = UserRepository(session)
            user = repo.get_by_public_id(user_id)
            if user is None:
                return False, "user not found"
            return repo.check_quota(user, resource)

    def consume_quota(self, user_id: str, resource: str) -> None:
        """Consume one quota unit for the given resource."""
        with sync_session_scope() as session:
            repo = UserRepository(session)
            user = repo.get_by_public_id(user_id)
            if user is None:
                raise KeyError(user_id)
            repo.consume_quota(user, resource)

    def usage_summary(self, user_id: str) -> dict[str, Any]:
        """Return token usage events aggregated from the JSON store."""
        return self._store.usage_summary(user_id)

    def admin_overview(self) -> dict[str, Any]:
        """Return admin metrics combining PostgreSQL users and JSON usage events."""
        with sync_session_scope() as session:
            repo = UserRepository(session)
            users = [repo.to_api_dict(user) for user in repo.list_all()]
        return self._store.admin_overview(users)

    def record_usage_event(self, **payload: Any) -> None:
        """Persist one LLM usage event and update token counters on the user row."""
        self._store.record_usage_event(**payload)
        user_id = str(payload.get("user_id") or "")
        total_tokens = int(payload.get("total_tokens") or 0)
        if not user_id or total_tokens <= 0:
            return
        with sync_session_scope() as session:
            repo = UserRepository(session)
            user = repo.get_by_public_id(user_id)
            if user is None:
                return
            repo.add_token_usage(user, total_tokens)


class PostgresTeamRepository:
    """Team operations that combine PostgreSQL users with JSON organization data."""

    def __init__(self, store: Any, identity_repository: PostgresIdentityRepository) -> None:
        self._store = store
        self._identity_repository = identity_repository

    def get_team_profile(self, user_id: str) -> dict[str, Any]:
        """Return the organization profile for the current user."""
        user = self._identity_repository.get_user_by_id(user_id)
        if user is None:
            raise KeyError(user_id)
        return self._store.get_team_profile_for_user(user)

    def rename_organization(self, user_id: str, organization_name: str) -> dict[str, Any]:
        """Rename the user's organization in JSON storage and PostgreSQL."""
        user = self._identity_repository.get_user_by_id(user_id)
        if user is None:
            raise KeyError(user_id)
        with sync_session_scope() as session:
            repo = UserRepository(session)
            db_user = repo.get_by_public_id(user_id)
            if db_user is None:
                raise KeyError(user_id)
            repo.update_organization_name(db_user, organization_name)
        return self._store.rename_organization_for_user(user, organization_name)

    def add_team_member(self, user_id: str, **payload: Any) -> dict[str, Any]:
        """Add a team member to the JSON-backed organization roster."""
        user = self._identity_repository.get_user_by_id(user_id)
        if user is None:
            raise KeyError(user_id)
        return self._store.add_team_member_for_user(
            user,
            name=str(payload.get("name") or ""),
            email=str(payload.get("email") or ""),
            role=str(payload.get("role") or "viewer"),
        )

    def update_knowledge_scope(self, user_id: str, scope: str) -> dict[str, Any]:
        """Update the organization knowledge scope for the current user."""
        user = self._identity_repository.get_user_by_id(user_id)
        if user is None:
            raise KeyError(user_id)
        return self._store.update_knowledge_scope_for_user(user, scope)


class PostgresProjectRepository:
    """Project metadata stored in JSON, keyed by PostgreSQL user profiles."""

    def __init__(self, store: Any, identity_repository: PostgresIdentityRepository) -> None:
        self._store = store
        self._identity_repository = identity_repository

    def sync_project_session(self, **payload: Any) -> dict[str, Any]:
        """Sync one project/session record for a user."""
        user_id = str(payload["user_id"])
        user = self._identity_repository.get_user_by_id(user_id)
        if user is None:
            raise KeyError(user_id)
        return self._store.sync_project_for_user(
            user,
            project_id=str(payload["project_id"]),
            project_title=str(payload["project_title"]),
            scenario_id=str(payload.get("scenario_id") or ""),
            session_id=str(payload["session_id"]),
            session_title=str(payload["session_title"]),
            session_subtitle=str(payload.get("session_subtitle") or ""),
            attachment_count=int(payload.get("attachment_count") or 0),
        )

    def list_projects(self, user_id: str) -> dict[str, Any]:
        """List projects visible to the user's organization."""
        user = self._identity_repository.get_user_by_id(user_id)
        if user is None:
            raise KeyError(user_id)
        return self._store.list_projects_for_user(user)
