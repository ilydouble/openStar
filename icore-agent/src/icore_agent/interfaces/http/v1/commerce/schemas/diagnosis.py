"""Commerce diagnosis API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CommerceDiagnosisRequest(BaseModel):
    """Request body for creating a Commerce diagnosis."""

    file_uuid: str = Field(..., min_length=1, max_length=128)
    locale: str = Field(default="zh-CN", max_length=16)


class CommerceSampleDiagnosisRequest(BaseModel):
    """Request body for creating a sample Commerce diagnosis."""

    locale: str = Field(default="zh-CN", max_length=16)


class CommerceDiagnosisResponse(BaseModel):
    """Response body for one generated Commerce diagnosis."""

    diagnosis_id: str
    agent_profile: str
    source_file: dict[str, Any]
    metrics: dict[str, Any]
    risks: list[dict[str, Any]]
    tasks: list[dict[str, Any]]
    report_summary: str
