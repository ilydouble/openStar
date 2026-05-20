"""Application service for usage and quota event recording."""

from __future__ import annotations

from typing import Any, Protocol


class UsageRepository(Protocol):
    """Persistence contract used by usage recording flows."""

    def record_usage_event(self, **payload: Any) -> None: ...


class UsageService:
    """Normalize token usage payloads before they reach infrastructure code."""

    def __init__(self, repository: UsageRepository) -> None:
        """Create a usage service backed by one usage repository."""
        self._repository = repository

    def record_llm_usage(
        self,
        *,
        user_id: str,
        session_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
    ) -> None:
        """Persist one LLM usage event with the current estimated cost formula."""
        self._repository.record_usage_event(
            user_id=user_id,
            session_id=session_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost=round(total_tokens / 1_000_000 * 2.0, 6),
        )
