"""Dependency providers shared across API routers."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from ..application.account import AccountService
from ..application.billing import BillingService
from ..application.knowledge import KnowledgeService
from ..application.usage import UsageService
from ..config import settings
from ..control_plane import control_plane_store
from ..infrastructure.control_plane import (
    ControlPlaneAccountRepository,
    ControlPlaneBillingRepository,
    ControlPlaneUsageRepository,
)
from ..memory.chroma_store import add_documents, get_collection, list_documents

account_repository = ControlPlaneAccountRepository(control_plane_store)
usage_repository = ControlPlaneUsageRepository(control_plane_store)
billing_repository = ControlPlaneBillingRepository(control_plane_store)

account_service = AccountService(account_repository, usage_store=usage_repository)
billing_service = BillingService(
    billing_repository,
    settings.icore_base_url or "http://localhost:8080",
)
usage_service = UsageService(usage_repository)
knowledge_service = KnowledgeService(
    add_documents=add_documents,
    list_documents=list_documents,
    get_collection=get_collection,
    rag_chunk_size=settings.rag_chunk_size,
    rag_chunk_overlap=settings.rag_chunk_overlap,
    file_size_limit_mb=settings.file_ops_max_size_mb,
)


def get_account_service() -> AccountService:
    """Return the singleton account service used by HTTP handlers."""
    return account_service


def get_billing_service() -> BillingService:
    """Return the singleton billing service used by HTTP handlers."""
    return billing_service


def get_usage_service() -> UsageService:
    """Return the singleton usage service used by infrastructure and app wiring."""
    return usage_service


def get_knowledge_service() -> KnowledgeService:
    """Return the singleton knowledge service used by HTTP handlers."""
    return knowledge_service


def get_current_user(
    authorization: str = Header(default=""),
    service: AccountService = Depends(get_account_service),
) -> dict:
    """Resolve the authenticated user from the bearer token header."""
    try:
        return service.get_current_user(authorization)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
