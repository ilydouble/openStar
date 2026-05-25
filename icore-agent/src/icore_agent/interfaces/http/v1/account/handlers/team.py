"""Team management handlers."""

from fastapi import Depends

from icore_agent.application.account import AccountService
from icore_agent.domain.user import AuthenticatedUser

from ...dependencies import get_account_service, get_current_user
from ..schemas.team import KnowledgeScopeRequest, OrganizationRenameRequest, TeamMemberRequest


async def get_team(
    user: AuthenticatedUser = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
) -> dict:
    """Return the current user's team summary."""
    return service.get_team(user.public_id)


async def rename_team(
    req: OrganizationRenameRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
) -> dict:
    """Rename the current user's organization."""
    return service.rename_team(user.public_id, req.organization_name)


async def add_team_member(
    req: TeamMemberRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
) -> dict:
    """Add a member to the current user's team."""
    member = service.add_team_member(
        user.public_id, name=req.name, email=req.email, role=req.role
    )
    return {"member": member}


async def update_team_knowledge_scope(
    req: KnowledgeScopeRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
) -> dict:
    """Update the team's default knowledge visibility scope."""
    return service.update_team_knowledge_scope(user.public_id, req.scope)
