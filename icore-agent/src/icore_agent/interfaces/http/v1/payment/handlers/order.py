"""Order handlers."""

from fastapi import Depends

from icore_agent.domain.user import AuthenticatedUser

from ...dependencies import get_current_user


async def get_user_orders(
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[dict]:
    """Return orders for the current user."""
    _ = user
    return []
