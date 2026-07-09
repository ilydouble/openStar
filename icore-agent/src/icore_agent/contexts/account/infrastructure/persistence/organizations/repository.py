"""SQLAlchemy repository for organizations and members."""

from __future__ import annotations

import time
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from icore_agent.contexts.account.domain.user import UserProfile

from .models import OrgMember, Organization


class SqlAlchemyOrganizationRepository:
    """Persist organization and membership metadata."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_public_id(self, public_id: str) -> Organization | None:
        """Load one organization by external id."""
        result = self._session.execute(
            select(Organization)
            .options(selectinload(Organization.members))
            .where(Organization.public_id == public_id)
        )
        return result.scalar_one_or_none()

    def ensure_for_user(self, user: UserProfile) -> Organization:
        """Create or load the organization referenced by one user profile."""
        org_public_id = (user.organization_id or "").strip()
        if not org_public_id:
            org_public_id = f"org_{uuid.uuid4().hex[:12]}"
        existing = self.get_by_public_id(org_public_id)
        if existing is not None:
            return existing

        now = int(time.time())
        org_name = (
            user.organization_name or f"{user.name or 'Team'} Team").strip()
        organization = Organization(
            public_id=org_public_id,
            name=org_name,
            knowledge_scope="organization",
            owner_user_id=user.public_id,
            created_at=int(user.created_at or now),
            updated_at=now,
        )
        self._session.add(organization)
        self._session.flush()
        self._session.add(
            OrgMember(
                org_id=organization.id,
                member_public_id=user.public_id,
                user_id=user.public_id,
                name=user.name,
                email=user.email,
                role=(user.roles or ["owner"])[0],
                status="active",
                created_at=now,
            )
        )
        self._session.flush()
        return organization

    def rename(self, organization: Organization, name: str) -> Organization:
        """Rename one organization."""
        organization.name = name.strip()
        organization.updated_at = int(time.time())
        self._session.flush()
        return organization

    def update_knowledge_scope(self, organization: Organization, scope: str) -> Organization:
        """Update the knowledge scope for one organization."""
        organization.knowledge_scope = scope
        organization.updated_at = int(time.time())
        self._session.flush()
        return organization

    def add_member(
        self,
        organization: Organization,
        *,
        name: str,
        email: str,
        role: str,
    ) -> dict[str, Any]:
        """Invite one member to an organization."""
        now = int(time.time())
        member = OrgMember(
            org_id=organization.id,
            member_public_id=f"member_{uuid.uuid4().hex[:12]}",
            user_id=None,
            name=name.strip(),
            email=email.strip().lower(),
            role=role.strip() or "viewer",
            status="invited",
            created_at=now,
        )
        organization.updated_at = now
        self._session.add(member)
        self._session.flush()
        return _serialize_member(member)

    @staticmethod
    def team_profile(organization: Organization, current_user_id: str) -> dict[str, Any]:
        """Build the API team profile payload."""
        return {
            "organization": {
                "id": organization.public_id,
                "name": organization.name,
                "knowledge_scope": organization.knowledge_scope,
            },
            "members": [_serialize_member(member) for member in organization.members],
            "current_user_id": current_user_id,
        }


def _serialize_member(member: OrgMember) -> dict[str, Any]:
    """Convert one membership row into the account API payload."""
    return {
        "user_id": member.member_public_id,
        "name": member.name,
        "email": member.email,
        "role": member.role,
        "status": member.status,
        "created_at": member.created_at,
    }
