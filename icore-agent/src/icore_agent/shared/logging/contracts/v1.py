"""Version 1 JSON contract for the internal logging service."""

from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class LogLevel(StrEnum):
    """LogLevel defines the severity values accepted by logging-service."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    AUDIT = "AUDIT"


class LogEvent(BaseModel):
    """LogEvent is the JSON payload shared by backend and logging-service."""

    event_id: str
    timestamp: datetime
    level: LogLevel
    service: str
    message: str
    trace_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class LogEventIngestRequest(BaseModel):
    """LogEventIngestRequest wraps one event for the HTTP ingest endpoint."""

    event: LogEvent


class LogEventBatchIngestRequest(BaseModel):
    """LogEventBatchIngestRequest wraps multiple events for batch ingestion."""

    events: list[LogEvent]


class LogEventIngestResult(BaseModel):
    """LogEventIngestResult reports how many events were accepted."""

    accepted: int


def model_to_json_dict(model: BaseModel) -> dict[str, Any]:
    """Return a JSON-ready dict on both Pydantic v1 and v2."""
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")  # type: ignore[attr-defined]
    return json.loads(model.model_dump_json())
