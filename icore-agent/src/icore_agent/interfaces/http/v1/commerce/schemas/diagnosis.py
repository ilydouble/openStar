"""Commerce diagnosis API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class CommerceDiagnosisRequest(BaseModel):
    """Request body for creating a Commerce diagnosis."""

    file_uuid: str | None = Field(default=None, min_length=1, max_length=128)
    file_uuids: list[str] = Field(default_factory=list, max_length=16)
    locale: str = Field(default="zh-CN", max_length=16)

    @model_validator(mode="after")
    def require_at_least_one_file(self) -> "CommerceDiagnosisRequest":
        """Require at least one uploaded CSV reference."""
        if not self.normalized_file_uuids:
            raise ValueError("At least one CSV file is required")
        return self

    @property
    def normalized_file_uuids(self) -> list[str]:
        """Return de-duplicated upload UUIDs from legacy and batch fields."""
        raw_values = list(self.file_uuids or [])
        if self.file_uuid:
            raw_values.append(self.file_uuid)
        normalized: list[str] = []
        for raw_value in raw_values:
            value = str(raw_value or "").strip()
            if value and value not in normalized:
                normalized.append(value)
        return normalized


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
