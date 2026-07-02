"""Commerce API router."""

from fastapi import APIRouter

from ..envelope import ApiEnvelopeRoute
from .handlers import (
    create_commerce_diagnosis,
    create_sample_commerce_diagnosis,
    get_latest_commerce_diagnosis,
)
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
router.post(
    "/diagnoses/sample",
    response_model=CommerceDiagnosisResponse,
    summary="Create a sample Commerce operating diagnosis",
)(create_sample_commerce_diagnosis)
router.get(
    "/diagnoses/latest",
    response_model=CommerceDiagnosisResponse,
    summary="Read the latest persisted Commerce operating diagnosis",
)(get_latest_commerce_diagnosis)
