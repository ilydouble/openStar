"""Application service for organization and project workspace metadata."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from icore_agent.contexts.account.application.usage.policy import current_timestamp
from icore_agent.contexts.account.domain.user import UserProfile
from icore_agent.contexts.account.infrastructure.cache.workspace_cache import workspace_cache
from icore_agent.contexts.account.infrastructure.persistence.organizations.repository import (
    SqlAlchemyOrganizationRepository,
)
from icore_agent.contexts.account.infrastructure.persistence.projects.repository import (
    SqlAlchemyProjectRepository,
)
from icore_agent.infrastructure.persistence.sqlalchemy.sync_session import sync_session_scope
from icore_agent.contexts.account.infrastructure.persistence.users.sqlalchemy_repository import (
    SqlAlchemyUserRepository,
)


class WorkspaceMetadataService:
    """Coordinate PostgreSQL workspace metadata with Redis caching."""

    def ensure_organization_for_user(self, user: UserProfile) -> UserProfile:
        """Ensure the user's organization exists in PostgreSQL."""
        with sync_session_scope() as session:
            users = SqlAlchemyUserRepository(session)
            orgs = SqlAlchemyOrganizationRepository(session)
            organization = orgs.ensure_for_user(user)
            if user.organization_id != organization.public_id or (
                user.organization_name or ""
            ) != organization.name:
                return users.save(
                    replace(
                        user,
                        organization_id=organization.public_id,
                        organization_name=organization.name,
                        updated_at=current_timestamp(),
                    )
                )
        return user

    def create_organization_for_user(self, user: UserProfile) -> None:
        """Create organization metadata for a newly registered user."""
        self.ensure_organization_for_user(user)
        workspace_cache.invalidate_user(user.public_id)

    def get_team_profile(self, user_id: str) -> dict[str, Any]:
        """Return the team profile, using Redis as a fast path when available."""
        cached = workspace_cache.get_team_profile(user_id)
        if cached is not None:
            return cached

        with sync_session_scope() as session:
            users = SqlAlchemyUserRepository(session)
            orgs = SqlAlchemyOrganizationRepository(session)
            user = users.get_by_public_id(user_id)
            if user is None:
                raise KeyError(user_id)
            user = self.ensure_organization_for_user(user)
            organization = orgs.get_by_public_id(user.organization_id or "")
            if organization is None:
                raise KeyError(user_id)
            payload = orgs.team_profile(organization, user_id)

        workspace_cache.set_team_profile(user_id, payload)
        return payload

    def rename_organization(self, user_id: str, organization_name: str) -> dict[str, Any]:
        """Rename the current user's organization."""
        with sync_session_scope() as session:
            users = SqlAlchemyUserRepository(session)
            orgs = SqlAlchemyOrganizationRepository(session)
            user = users.get_by_public_id(user_id)
            if user is None:
                raise KeyError(user_id)
            organization = orgs.get_by_public_id(user.organization_id or "")
            if organization is None:
                raise KeyError(user_id)
            orgs.rename(organization, organization_name)
            users.save(
                replace(
                    user,
                    organization_name=organization_name.strip(),
                    updated_at=current_timestamp(),
                )
            )
            payload = orgs.team_profile(organization, user_id)

        workspace_cache.invalidate_user(user_id)
        workspace_cache.set_team_profile(user_id, payload)
        return payload

    def add_team_member(self, user_id: str, **payload: Any) -> dict[str, Any]:
        """Invite one member to the user's organization."""
        with sync_session_scope() as session:
            users = SqlAlchemyUserRepository(session)
            orgs = SqlAlchemyOrganizationRepository(session)
            user = users.get_by_public_id(user_id)
            if user is None:
                raise KeyError(user_id)
            organization = orgs.get_by_public_id(user.organization_id or "")
            if organization is None:
                raise KeyError(user_id)
            member = orgs.add_member(
                organization,
                name=str(payload.get("name") or ""),
                email=str(payload.get("email") or ""),
                role=str(payload.get("role") or "viewer"),
            )

        workspace_cache.invalidate_user(user_id)
        return member

    def update_knowledge_scope(self, user_id: str, scope: str) -> dict[str, Any]:
        """Update the knowledge scope for the user's organization."""
        with sync_session_scope() as session:
            users = SqlAlchemyUserRepository(session)
            orgs = SqlAlchemyOrganizationRepository(session)
            user = users.get_by_public_id(user_id)
            if user is None:
                raise KeyError(user_id)
            organization = orgs.get_by_public_id(user.organization_id or "")
            if organization is None:
                raise KeyError(user_id)
            orgs.update_knowledge_scope(organization, scope)
            payload = orgs.team_profile(organization, user_id)

        workspace_cache.invalidate_user(user_id)
        workspace_cache.set_team_profile(user_id, payload)
        return payload

    def sync_project_session(self, **payload: Any) -> dict[str, Any]:
        """Persist one project/session metadata record."""
        user_id = str(payload["user_id"])
        with sync_session_scope() as session:
            users = SqlAlchemyUserRepository(session)
            orgs = SqlAlchemyOrganizationRepository(session)
            projects = SqlAlchemyProjectRepository(session)
            user = users.get_by_public_id(user_id)
            if user is None:
                raise KeyError(user_id)
            user = self.ensure_organization_for_user(user)
            organization = orgs.get_by_public_id(user.organization_id or "")
            if organization is None:
                raise KeyError(user_id)
            project = projects.upsert_project_session(
                org_id=organization.id,
                owner_user_id=user_id,
                project_id=str(payload["project_id"]),
                project_title=str(payload["project_title"]),
                scenario_id=str(payload.get("scenario_id") or ""),
                session_id=str(payload["session_id"]),
                session_title=str(payload["session_title"]),
                session_subtitle=str(payload.get("session_subtitle") or ""),
                attachment_count=int(payload.get("attachment_count") or 0),
            )

        workspace_cache.invalidate_user(user_id)
        return project

    def list_projects(self, user_id: str) -> dict[str, Any]:
        """List projects visible to the user's organization."""
        cached = workspace_cache.get_project_list(user_id)
        if cached is not None:
            return cached

        with sync_session_scope() as session:
            users = SqlAlchemyUserRepository(session)
            orgs = SqlAlchemyOrganizationRepository(session)
            projects = SqlAlchemyProjectRepository(session)
            user = users.get_by_public_id(user_id)
            if user is None:
                raise KeyError(user_id)
            user = self.ensure_organization_for_user(user)
            organization = orgs.get_by_public_id(user.organization_id or "")
            if organization is None:
                raise KeyError(user_id)
            rows = projects.list_for_org(organization.id)
            payload = projects.list_payload(rows)

        workspace_cache.set_project_list(user_id, payload)
        return payload
