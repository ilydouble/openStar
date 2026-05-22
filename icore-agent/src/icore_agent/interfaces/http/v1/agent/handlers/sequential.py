"""Sequential task handlers."""

import asyncio

from fastapi import Depends, HTTPException

from icore_agent.domain.user import AuthenticatedUser
from icore_agent.application.chat.sequential import SequentialAgent
from icore_agent.shared.logging.app_logger import get_logger

from ...dependencies import get_current_user
from ..schemas.sequential import SequentialRequest, SequentialResponse

log = get_logger(__name__)


async def run_sequential(
    req: SequentialRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> SequentialResponse:
    """Run a sequential bash task using the mini-SWE-agent environment."""
    _ = user
    log.info("sequential_request", task_preview=req.task[:100])

    if req.use_docker:
        from icore_agent.application.chat.sequential.environment import DockerEnvironment

        env = DockerEnvironment()
    else:
        from icore_agent.application.chat.sequential.environment import LocalEnvironment

        env = LocalEnvironment()

    agent = SequentialAgent(environment=env)

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, agent.run, req.task)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return SequentialResponse(
        status=result.status,
        output=result.output,
        steps=result.steps,
    )
