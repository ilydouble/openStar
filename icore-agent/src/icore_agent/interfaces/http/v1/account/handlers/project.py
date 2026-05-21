"""Project synchronization handlers."""

from fastapi import Depends

from icore_agent.application.account import AccountService

from ...dependencies import get_account_service, get_current_user
from ..schemas.project import ProjectSyncRequest


async def sync_project(
    req: ProjectSyncRequest,
    user: dict = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
) -> dict:
    """Synchronize a client project/session summary into the account domain."""
    project = service.sync_project(
        user_id=user["id"],
        project_id=req.project_id,
        project_title=req.project_title,
        scenario_id=req.scenario_id,
        session_id=req.session_id,
        session_title=req.session_title,
        session_subtitle=req.session_subtitle,
        attachment_count=req.attachment_count,
    )
    return {"project": project}


async def list_projects(
    user: dict = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
) -> dict:
    """List projects visible to the current user."""
    return service.list_projects(user["id"])
