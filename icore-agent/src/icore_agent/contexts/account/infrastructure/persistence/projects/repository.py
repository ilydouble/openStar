"""SQLAlchemy repository for projects and project session metadata."""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import Project, ProjectSession


class SqlAlchemyProjectRepository:
    """Persist project metadata and linked workspace sessions."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_org_and_public_id(self, org_id: int, public_id: str) -> Project | None:
        """Load one project scoped to an organization."""
        result = self._session.execute(
            select(Project)
            .options(selectinload(Project.sessions))
            .where(Project.org_id == org_id, Project.public_id == public_id)
        )
        return result.scalar_one_or_none()

    def list_for_org(self, org_id: int) -> list[Project]:
        """Return all projects for one organization."""
        result = self._session.execute(
            select(Project)
            .options(selectinload(Project.sessions))
            .where(Project.org_id == org_id)
            .order_by(Project.updated_at.desc())
        )
        return list(result.scalars().all())

    def upsert_project_session(
        self,
        *,
        org_id: int,
        owner_user_id: str,
        project_id: str,
        project_title: str,
        scenario_id: str,
        session_id: str,
        session_title: str,
        session_subtitle: str,
        attachment_count: int,
    ) -> dict[str, Any]:
        """Create or update one project and its linked session metadata."""
        now = int(time.time())
        project = self.get_by_org_and_public_id(org_id, project_id)
        if project is None:
            project = Project(
                public_id=project_id,
                org_id=org_id,
                owner_user_id=owner_user_id,
                title=project_title,
                scenario_id=scenario_id,
                created_at=now,
                updated_at=now,
            )
            self._session.add(project)
            self._session.flush()
        else:
            project.title = project_title or project.title
            project.scenario_id = scenario_id or project.scenario_id
            project.updated_at = now

        session_row = next(
            (item for item in project.sessions if item.session_public_id == session_id),
            None,
        )
        if session_row is None:
            session_row = ProjectSession(
                project_id=project.id,
                session_public_id=session_id,
                title=session_title,
                subtitle=session_subtitle,
                attachment_count=max(int(attachment_count or 0), 0),
                updated_at=now,
            )
            project.sessions.append(session_row)
        else:
            session_row.title = session_title or session_row.title
            session_row.subtitle = session_subtitle
            session_row.attachment_count = max(int(attachment_count or 0), 0)
            session_row.updated_at = now

        self._session.flush()
        return serialize_project(project)

    @staticmethod
    def list_payload(projects: list[Project]) -> dict[str, Any]:
        """Build the account API project list payload."""
        serialized = [serialize_project(project) for project in projects]
        serialized.sort(key=lambda item: item["updated_at"], reverse=True)
        recent_sessions: list[dict[str, Any]] = []
        for project in serialized:
            for session in project["sessions"]:
                recent_sessions.append(
                    {
                        **session,
                        "project_id": project["id"],
                        "project_title": project["title"],
                        "scenario_id": project.get("scenario_id", ""),
                    }
                )
        recent_sessions.sort(key=lambda item: item["updated_at"], reverse=True)
        return {
            "projects": serialized[:10],
            "recent_sessions": recent_sessions[:12],
        }


def serialize_project(project: Project) -> dict[str, Any]:
    """Serialize one project row for API responses."""
    sessions = sorted(
        project.sessions,
        key=lambda item: item.updated_at,
        reverse=True,
    )
    session_payload = [
        {
            "session_id": item.session_public_id,
            "title": item.title,
            "subtitle": item.subtitle,
            "attachment_count": item.attachment_count,
            "updated_at": item.updated_at,
        }
        for item in sessions
    ]
    return {
        "id": project.public_id,
        "title": project.title,
        "scenario_id": project.scenario_id,
        "updated_at": project.updated_at,
        "owner_user_id": project.owner_user_id,
        "sessions_count": len(session_payload),
        "assets_count": sum(int(item["attachment_count"]) for item in session_payload),
        "sessions": session_payload[:6],
    }
