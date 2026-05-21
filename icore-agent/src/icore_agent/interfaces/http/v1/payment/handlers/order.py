"""Order handlers."""

from fastapi import Depends

from ...dependencies import get_current_user


async def get_user_orders(
    user: dict = Depends(get_current_user),
) -> list[dict]:
    """Return orders for the current user."""
    _ = user
    return []
