"""Current account and usage handlers."""

from fastapi import Depends, HTTPException

from ....application.account import AccountService
from ...dependencies import get_account_service, get_current_user


async def get_me(user: dict = Depends(get_current_user)) -> dict:
    """Return the authenticated user payload."""
    return user


async def get_usage_summary(
    user: dict = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
) -> dict:
    """Return the current user's usage summary."""
    return service.get_usage_summary(user["id"])


async def get_admin_overview(
    user: dict = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
) -> dict:
    """Return an admin overview for users with permission."""
    try:
        return service.get_admin_overview(user)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
