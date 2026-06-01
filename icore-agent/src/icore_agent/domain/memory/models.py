"""Domain models for durable cross-session user memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class UserMemoryProfile:
    """Stable user-scoped memory profile and extraction counters."""

    user_id: str
    profile: dict[str, Any] = field(default_factory=dict)
    maintenance_version: int = 0
    extract_count: int = 0
    turns_since_extract: int = 0
    last_maintained_at: int = 0
    created_at: int = 0
    updated_at: int = 0


@dataclass(slots=True)
class UserMemoryFact:
    """One structured memory fact with scoring metadata."""

    user_id: str
    category: str
    key: str
    value: str
    id: int | None = None
    status: str = "active"
    source: str = "inferred"
    confidence: float = 0.5
    salience: float = 0.5
    access_count: int = 0
    last_accessed_at: int = 0
    last_confirmed_at: int = 0
    expires_at: int | None = None
    supersedes_id: int | None = None
    source_session_id: str | None = None
    created_at: int = 0
    updated_at: int = 0


@dataclass(frozen=True, slots=True)
class TurnMemoryContext:
    """Turn-scoped inputs used to rank memory facts for prompt injection."""

    message: str
    session_summary: str | None = None
    agent_hint: str | None = None


@dataclass(frozen=True, slots=True)
class MemoryFactCandidate:
    """Candidate fact extracted from one session slice."""

    category: str
    key: str
    value: str
    source: str = "inferred"
    confidence: float = 0.5
    salience: float = 0.5


@dataclass(frozen=True, slots=True)
class MemoryExtractionResult:
    """Structured output from the memory extract phase."""

    profile_updates: dict[str, Any] = field(default_factory=dict)
    candidates: tuple[MemoryFactCandidate, ...] = ()
