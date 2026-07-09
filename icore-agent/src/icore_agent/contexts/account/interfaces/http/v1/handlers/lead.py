"""Lead capture handlers."""

from fastapi import Depends

from icore_agent.contexts.account.application import AccountService

from icore_agent.interfaces.http.v1.dependencies import get_account_service
from ..schemas.lead import LeadCaptureRequest


async def capture_lead(
    req: LeadCaptureRequest,
    service: AccountService = Depends(get_account_service),
) -> dict:
    """Capture a sales or upgrade lead."""
    lead = service.capture_lead(
        name=req.name,
        email=req.email,
        company=req.company,
        team_size=req.team_size,
        use_case=req.use_case,
        needs_byok=req.needs_byok,
        needs_private_deploy=req.needs_private_deploy,
        source=req.source,
        intent=req.intent,
    )
    return {"lead": lead}
