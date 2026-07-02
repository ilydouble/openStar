"""Commerce API router."""

from fastapi import APIRouter

from ..envelope import ApiEnvelopeRoute
from .handlers import create_commerce_diagnosis
from .schemas import CommerceDiagnosisResponse

router = APIRouter(
    prefix="/api/v1/commerce",
    tags=["commerce"],
    route_class=ApiEnvelopeRoute,
)

router.post(
    "/diagnoses",
    response_model=CommerceDiagnosisResponse,
    summary="Create a Commerce operating diagnosis from an uploaded CSV",
)(create_commerce_diagnosis)
