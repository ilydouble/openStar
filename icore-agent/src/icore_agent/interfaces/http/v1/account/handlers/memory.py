"""Account memory management handlers."""

from fastapi import Depends, HTTPException

from icore_agent.application.memory import UserMemoryService
from icore_agent.domain.user import AuthenticatedUser

from ...dependencies import get_current_user, get_user_memory_service
from ..schemas.memory import UpdateMemoryFactRequest


def _memory_http_error(exc: Exception) -> HTTPException:
    """Map memory domain errors to HTTP responses."""
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    raise exc


async def get_memory(
    user: AuthenticatedUser = Depends(get_current_user),
    service: UserMemoryService = Depends(get_user_memory_service),
) -> dict:
    """Return the current user's durable memory profile and active facts."""
    return service.list_account_memory(user.public_id)


async def update_memory_fact(
    fact_id: int,
    req: UpdateMemoryFactRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    service: UserMemoryService = Depends(get_user_memory_service),
) -> dict:
    """Update one owned memory fact value."""
    try:
        return service.update_fact_value(user.public_id, fact_id, req.value)
    except (LookupError, ValueError) as exc:
        raise _memory_http_error(exc) from exc


async def delete_memory_fact(
    fact_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    service: UserMemoryService = Depends(get_user_memory_service),
) -> dict:
    """Delete one owned memory fact."""
    try:
        service.delete_fact(user.public_id, fact_id)
    except LookupError as exc:
        raise _memory_http_error(exc) from exc
    return {"deleted": True, "fact_id": fact_id}
