"""Application service for durable cross-session user memory."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from icore_agent.application.usage.policy import current_timestamp
from icore_agent.domain.memory import (
    MemoryExtractionResult,
    MemoryFactCandidate,
    TurnMemoryContext,
    UserMemoryFact,
    UserMemoryProfile,
    UserMemoryRepository,
)
from icore_agent.shared.logging.app_logger import get_logger

from . import consolidation, policy

log = get_logger(__name__)

MemoryExtractor = Callable[..., MemoryExtractionResult]


class UserMemoryService:
    """Load, rank, and extract durable user memory across sessions."""

    def __init__(
        self,
        repository: UserMemoryRepository,
        *,
        extractor: MemoryExtractor | None = None,
    ) -> None:
        """Create a user memory service backed by one repository."""
        self._repository = repository
        self._extractor = extractor or consolidation.extract_memory_from_session

    def build_memory_prompt(
        self,
        user_id: str,
        turn: TurnMemoryContext,
    ) -> str | None:
        """Return the bounded user-memory prompt section for one turn."""
        try:
            profile_row = self._repository.get_or_create_profile(user_id)
            facts = self._repository.list_active_facts(user_id)
            selected = policy.rank_facts_for_turn(facts, turn)
            if selected:
                now = current_timestamp()
                fact_ids = [
                    fact.id for fact in selected if fact.id is not None]
                self._repository.mark_facts_accessed(fact_ids, accessed_at=now)
            return policy.build_user_memory_prompt(profile_row.profile, selected)
        except Exception as exc:
            log.warning("user_memory_prompt_failed",
                        user_id=user_id, error=str(exc))
            return None

    def should_extract_on_compression(self, *, session_compressed: bool) -> bool:
        """Return whether durable memory should run after a turn due to compression."""
        log.info(
            "user_memory_turn_completed",
            session_compressed=session_compressed,
            should_extract=session_compressed,
        )
        return session_compressed

    async def extract_on_session_end(
        self,
        *,
        user_id: str,
        session_id: str,
        session_summary: str | None,
        recent_messages: list[dict[str, str]],
    ) -> None:
        """Extract durable memory once when a chat session ends."""
        if not policy.session_has_extractable_content(session_summary, recent_messages):
            log.info(
                "user_memory_extract_skipped",
                user_id=user_id,
                session_id=session_id,
                reason="empty_session",
            )
            return
        log.info(
            "user_memory_extract_session_end_scheduled",
            user_id=user_id,
            session_id=session_id,
        )
        await self.extract_from_session(
            user_id=user_id,
            session_id=session_id,
            session_summary=str(session_summary or ""),
            recent_messages=recent_messages,
        )

    async def extract_from_session(
        self,
        *,
        user_id: str,
        session_id: str,
        session_summary: str,
        recent_messages: list[dict[str, str]],
    ) -> None:
        """Run the extract phase asynchronously without blocking chat completion."""
        await asyncio.to_thread(
            self.extract_from_session_sync,
            user_id=user_id,
            session_id=session_id,
            session_summary=session_summary,
            recent_messages=recent_messages,
        )

    def extract_from_session_sync(
        self,
        *,
        user_id: str,
        session_id: str,
        session_summary: str,
        recent_messages: list[dict[str, str]],
    ) -> None:
        """Extract durable memory from one session slice and persist candidates."""
        log.info(
            "user_memory_extract_started",
            user_id=user_id,
            session_id=session_id,
            session_summary_chars=len(session_summary or ""),
            recent_message_count=len(recent_messages),
        )
        try:
            profile = self._repository.get_or_create_profile(user_id)
            result = self._extractor(
                profile=profile.profile,
                session_summary=session_summary,
                recent_messages=recent_messages,
            )
            saved_count = self._apply_extraction(
                user_id=user_id,
                session_id=session_id,
                profile=profile,
                result=result,
            )
            log.info(
                "user_memory_extract_finished",
                user_id=user_id,
                session_id=session_id,
                profile_update_keys=list(result.profile_updates.keys()),
                candidate_count=len(result.candidates),
                facts_saved=saved_count,
                active_fact_count=self._repository.count_active_facts(user_id),
            )
        except Exception as exc:
            log.warning(
                "user_memory_extract_failed",
                user_id=user_id,
                session_id=session_id,
                error=str(exc),
            )

    def _apply_extraction(
        self,
        *,
        user_id: str,
        session_id: str,
        profile: UserMemoryProfile,
        result: MemoryExtractionResult,
    ) -> int:
        """Persist profile updates and fact candidates from one extraction."""
        now = current_timestamp()
        saved_count = 0
        if result.profile_updates:
            profile.profile = policy.merge_profile(
                profile.profile, result.profile_updates)
            log.info(
                "user_memory_profile_updated",
                user_id=user_id,
                session_id=session_id,
                profile_keys=list(profile.profile.keys()),
            )
        profile.extract_count = int(profile.extract_count) + 1
        profile.updated_at = now
        self._repository.save_profile(profile)

        if not result.candidates and not result.profile_updates:
            log.warning(
                "user_memory_extract_no_persisted_changes",
                user_id=user_id,
                session_id=session_id,
            )

        for candidate in result.candidates:
            if self._apply_candidate(
                user_id=user_id,
                session_id=session_id,
                candidate=candidate,
                now=now,
            ):
                saved_count += 1
        return saved_count

    def _apply_candidate(
        self,
        *,
        user_id: str,
        session_id: str,
        candidate: MemoryFactCandidate,
        now: int,
    ) -> bool:
        """Apply supersession rules for one extracted fact candidate."""
        existing_matches = self._repository.list_active_facts_for_slot(
            user_id,
            candidate.category,
            candidate.key,
        )
        existing = existing_matches[0] if existing_matches else None
        if existing is not None and policy.values_equivalent(existing.value, candidate.value):
            existing.last_confirmed_at = now
            existing.updated_at = now
            existing.confidence = max(
                existing.confidence, candidate.confidence)
            existing.salience = max(existing.salience, candidate.salience)
            if candidate.source == "explicit":
                existing.source = "explicit"
            self._repository.save_fact(existing)
            for duplicate in existing_matches[1:]:
                duplicate.status = "superseded"
                duplicate.updated_at = now
                self._repository.save_fact(duplicate)
            log.info(
                "user_memory_fact_confirmed",
                user_id=user_id,
                session_id=session_id,
                category=candidate.category,
                key=candidate.key,
                fact_id=existing.id,
            )
            return True

        if existing is not None and not policy.should_supersede(existing, candidate.source):
            log.info(
                "user_memory_fact_rejected",
                user_id=user_id,
                session_id=session_id,
                category=candidate.category,
                key=candidate.key,
                reason="explicit_existing_blocks_inferred",
                existing_source=existing.source,
                candidate_source=candidate.source,
            )
            return False

        superseded_id = existing.id if existing is not None else None
        for match in existing_matches:
            match.status = "superseded"
            match.updated_at = now
            self._repository.save_fact(match)

        if self._repository.count_active_facts(user_id) >= policy.ACTIVE_FACT_CAP:
            log.warning(
                "user_memory_fact_cap_reached",
                user_id=user_id,
                session_id=session_id,
                category=candidate.category,
                key=candidate.key,
            )
            return False

        saved = self._repository.save_fact(UserMemoryFact(
            user_id=user_id,
            category=candidate.category,
            key=candidate.key,
            value=candidate.value,
            status="active",
            source=candidate.source,
            confidence=candidate.confidence,
            salience=candidate.salience,
            last_confirmed_at=now,
            source_session_id=session_id,
            supersedes_id=superseded_id,
            created_at=now,
            updated_at=now,
        ))
        log.info(
            "user_memory_fact_saved",
            user_id=user_id,
            session_id=session_id,
            category=candidate.category,
            key=candidate.key,
            fact_id=saved.id,
            source=candidate.source,
            supersedes_id=superseded_id,
        )
        return True

    def list_account_memory(self, user_id: str) -> dict[str, object]:
        """Return profile preferences and active facts for the account memory UI."""
        profile_row = self._repository.get_or_create_profile(user_id)
        facts = self._repository.list_active_facts(user_id)
        return {
            "profile": dict(profile_row.profile or {}),
            "facts": [_serialize_fact(fact) for fact in facts],
        }

    def update_fact_value(
        self,
        user_id: str,
        fact_id: int,
        value: str,
    ) -> dict[str, object]:
        """Update one owned fact value from the account memory manager."""
        fact = self._repository.get_active_fact_by_id(user_id, fact_id)
        if fact is None:
            raise LookupError("Memory fact not found")
        normalized = policy.normalize_fact_value(value)
        if not normalized:
            raise ValueError("Fact value cannot be empty")
        now = current_timestamp()
        fact.value = normalized
        fact.source = "explicit"
        fact.last_confirmed_at = now
        fact.updated_at = now
        saved = self._repository.save_fact(fact)
        log.info(
            "user_memory_fact_updated",
            user_id=user_id,
            fact_id=fact_id,
            category=saved.category,
            key=saved.key,
        )
        return _serialize_fact(saved)

    def delete_fact(self, user_id: str, fact_id: int) -> None:
        """Soft-delete one owned fact from the account memory manager."""
        fact = self._repository.get_active_fact_by_id(user_id, fact_id)
        if fact is None:
            raise LookupError("Memory fact not found")
        now = current_timestamp()
        fact.status = "superseded"
        fact.updated_at = now
        self._repository.save_fact(fact)
        log.info(
            "user_memory_fact_deleted",
            user_id=user_id,
            fact_id=fact_id,
            category=fact.category,
            key=fact.key,
        )


def _serialize_fact(fact: UserMemoryFact) -> dict[str, object]:
    """Convert one domain fact into an account API payload."""
    return {
        "id": int(fact.id),
        "category": fact.category,
        "key": fact.key,
        "value": fact.value,
        "confidence": float(fact.confidence),
        "salience": float(fact.salience),
        "source": fact.source,
        "last_confirmed_at": int(fact.last_confirmed_at),
        "updated_at": int(fact.updated_at),
    }
