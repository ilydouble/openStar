"""Account plan and BYOK handlers."""

from fastapi import Depends

from ....application.account import AccountService
from ...dependencies import get_account_service, get_current_user
from ..schemas.billing import ByokRequest


async def get_plan(
    user: dict = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
) -> dict:
    """Return the current user's account plan."""
    return service.get_plan(user["id"])


async def update_byok(
    req: ByokRequest,
    user: dict = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
) -> dict:
    """Update Bring Your Own Key settings for the current user."""
    return service.update_byok(user["id"], req.api_key, req.api_base, req.model)
