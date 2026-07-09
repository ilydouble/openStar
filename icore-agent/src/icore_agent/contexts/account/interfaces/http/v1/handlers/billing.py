"""Account plan and BYOK handlers."""

from fastapi import Depends

from icore_agent.contexts.account.application import AccountService
from icore_agent.contexts.account.domain.user import AuthenticatedUser

from icore_agent.interfaces.http.v1.dependencies import get_account_service, get_current_user
from ..users.serializers import serialize_byok
from ..schemas.billing import ByokRequest


async def get_plan(
    user: AuthenticatedUser = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
) -> dict:
    """Return the current user's account plan."""
    plan = service.get_plan(user.public_id)
    plan["byok"] = serialize_byok(plan.get("byok"))
    return plan


async def update_byok(
    req: ByokRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
) -> dict:
    """Update Bring Your Own Key settings for the current user."""
    result = service.update_byok(
        user.public_id, req.api_key, req.api_base, req.model)
    return serialize_byok(result)
