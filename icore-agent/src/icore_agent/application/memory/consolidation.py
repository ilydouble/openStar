"""LLM-backed extraction helpers for durable user memory."""

from __future__ import annotations

import json
import re
from typing import Any

import litellm

from icore_agent.config import settings
from icore_agent.domain.agent import ChatCompletionRole
from icore_agent.domain.memory import MemoryExtractionResult, MemoryFactCandidate
from icore_agent.shared.logging.app_logger import get_logger

from . import policy

log = get_logger(__name__)

_EXTRACT_SYSTEM = """
You extract durable user memory from one chat session slice.

Return ONLY valid JSON with this shape:
{
  "profile_updates": {"tone": "concise", "role": "solo seller", "domain": "e-commerce"},
  "candidates": [
    {
      "category": "work_context",
      "key": "primary_platform",
      "value": "Shopify",
      "source": "explicit",
      "confidence": 0.9,
      "salience": 0.8
    },
    {
      "category": "personal",
      "key": "name",
      "value": "Alex",
      "source": "explicit",
      "confidence": 0.95,
      "salience": 0.9
    },
    {
      "category": "personal",
      "key": "age",
      "value": "34",
      "source": "explicit",
      "confidence": 0.95,
      "salience": 0.85
    },
    {
      "category": "personal",
      "key": "location",
      "value": "US",
      "source": "explicit",
      "confidence": 0.9,
      "salience": 0.8
    }
  ]
}

Rules:
- Keep stable preferences, work context, goals, constraints, and explicit personal facts.
- Do NOT store document/file contents, attachment names, one-off task outputs, or transient details.
- Use source="explicit" only when the user clearly stated the fact themselves.
- category must be one of: preference, work_context, goal, constraint, personal.
- key must be a short snake_case identifier.
- value must be <= 200 characters.
- profile_updates is ONLY for stable work/style preferences:
  tone, role, domain, language, timezone, output_format, industry, team_size.
- Do NOT put name, age, location, pronouns, birthday, or nationality in profile_updates.
- When the user states their name, age, location, pronouns, or similar personal facts,
  store them in candidates with category="personal" and these canonical keys:
  name, age, location, pronouns, birthday, nationality.
- Put job title, role, and work domain in profile_updates.role or profile_updates.domain.
- If nothing durable was learned, return {"profile_updates": {}, "candidates": []}.
""".strip()

_ALLOWED_CATEGORIES = frozenset({
    "preference",
    "work_context",
    "goal",
    "constraint",
    "personal",
})

_CATEGORY_ALIASES = {
    "preferences": "preference",
    "work context": "work_context",
    "work-context": "work_context",
    "workcontext": "work_context",
    "goals": "goal",
    "constraints": "constraint",
    "persona": "personal",
    "personal_info": "personal",
    "identity": "personal",
    "demographics": "personal",
}

_RAW_PREVIEW_LIMIT = 2000


def build_extract_user_payload(
    *,
    profile: dict[str, Any],
    session_summary: str,
    recent_messages: list[dict[str, str]],
) -> str:
    """Build the user payload for one memory extraction call."""
    turns = "\n".join(
        f"{message['role'].upper()}: {message['content']}"
        for message in recent_messages
    )
    return (
        f"Existing profile:\n{json.dumps(profile or {}, ensure_ascii=False)}\n\n"
        f"Session summary:\n{session_summary or '(empty)'}\n\n"
        f"Recent turns:\n{turns or '(empty)'}"
    )


def parse_extract_response(raw: str) -> MemoryExtractionResult:
    """Parse and sanitize one LLM extraction response."""
    payload = _load_json_object(raw)
    raw_profile_updates = payload.get("profile_updates") or {}
    profile_updates, dropped_profile_keys = policy.normalize_profile_updates_with_trace(
        raw_profile_updates,
    )
    raw_candidates = payload.get("candidates") or []
    candidates: list[MemoryFactCandidate] = []
    rejected: list[dict[str, str]] = []
    seen_slots: set[tuple[str, str]] = set()

    if not isinstance(raw_candidates, list):
        rejected.append({
            "reason": "candidates_not_a_list",
            "detail": type(raw_candidates).__name__,
        })
        raw_candidates = []

    for index, item in enumerate(raw_candidates):
        candidate = _parse_candidate_item(item, index=index, rejected=rejected)
        if candidate is None:
            continue
        slot = (candidate.category, candidate.key)
        if slot in seen_slots:
            rejected.append({
                "reason": "duplicate_slot",
                "index": str(index),
                "category": candidate.category,
                "key": candidate.key,
            })
            continue
        seen_slots.add(slot)
        candidates.append(candidate)

    promoted_personal = policy.personal_facts_from_profile_updates(
        raw_profile_updates)
    for key, value in promoted_personal:
        slot = ("personal", key)
        if slot in seen_slots:
            continue
        seen_slots.add(slot)
        candidates.append(MemoryFactCandidate(
            category="personal",
            key=key,
            value=value,
            source="explicit",
            confidence=0.9,
            salience=0.85,
        ))

    log.info(
        "user_memory_extract_parsed",
        profile_update_keys=list(profile_updates.keys()),
        dropped_profile_keys=dropped_profile_keys,
        raw_candidate_count=len(raw_candidates),
        accepted_candidate_count=len(candidates),
        rejected_candidate_count=len(rejected),
        rejected_candidates=rejected[:10],
        promoted_personal_keys=[key for key, _value in promoted_personal],
    )
    return MemoryExtractionResult(
        profile_updates=profile_updates,
        candidates=tuple(candidates),
    )


def _parse_candidate_item(
    item: Any,
    *,
    index: int,
    rejected: list[dict[str, str]],
) -> MemoryFactCandidate | None:
    """Parse one raw candidate object from the LLM response."""
    if not isinstance(item, dict):
        rejected.append({
            "reason": "candidate_not_object",
            "index": str(index),
            "detail": type(item).__name__,
        })
        return None
    category = _normalize_category(str(item.get("category") or ""))
    key = policy.normalize_fact_key(str(item.get("key") or ""))
    value = policy.normalize_fact_value(str(item.get("value") or ""))
    if category not in _ALLOWED_CATEGORIES:
        rejected.append({
            "reason": "invalid_category",
            "index": str(index),
            "category": str(item.get("category") or ""),
            "key": str(item.get("key") or ""),
        })
        return None
    if not key:
        rejected.append({
            "reason": "empty_key",
            "index": str(index),
            "category": category,
        })
        return None
    if not value:
        rejected.append({
            "reason": "empty_value",
            "index": str(index),
            "category": category,
            "key": key,
        })
        return None
    source = str(item.get("source") or "inferred").strip().lower()
    if source not in {"explicit", "inferred"}:
        source = "inferred"
    return MemoryFactCandidate(
        category=category,
        key=key,
        value=value,
        source=source,
        confidence=_clamp_float(item.get("confidence"), default=0.5),
        salience=_clamp_float(item.get("salience"), default=0.5),
    )


def extract_memory_from_session(
    *,
    profile: dict[str, Any],
    session_summary: str,
    recent_messages: list[dict[str, str]],
) -> MemoryExtractionResult:
    """Call the configured model to extract durable memory candidates."""
    filtered = policy.filter_messages_for_extraction(recent_messages)
    log.info(
        "user_memory_extract_input",
        session_summary_chars=len(session_summary or ""),
        recent_message_count=len(recent_messages),
        filtered_message_count=len(filtered),
    )
    if not session_summary.strip() and not filtered:
        log.warning(
            "user_memory_extract_skipped_empty_input",
            session_summary_chars=0,
            filtered_message_count=0,
        )
        return MemoryExtractionResult()

    try:
        response = litellm.completion(
            model=settings.model_id,
            messages=[
                {"role": ChatCompletionRole.SYSTEM.value,
                    "content": _EXTRACT_SYSTEM},
                {
                    "role": ChatCompletionRole.USER.value,
                    "content": build_extract_user_payload(
                        profile=profile,
                        session_summary=session_summary,
                        recent_messages=filtered,
                    ),
                },
            ],
            max_tokens=700,
            temperature=0.1,
            **settings.litellm_kwargs(model_id=settings.model_id),
        )
        raw = str(response.choices[0].message.content or "").strip()
    except Exception as exc:
        log.warning(
            "user_memory_extract_llm_failed",
            model=settings.model_id,
            error=str(exc),
        )
        raise

    log.info(
        "user_memory_extract_llm_response",
        model=settings.model_id,
        raw_chars=len(raw),
        raw_preview=raw[:_RAW_PREVIEW_LIMIT],
    )
    try:
        return parse_extract_response(raw)
    except Exception as exc:
        log.warning(
            "user_memory_extract_parse_failed",
            model=settings.model_id,
            error=str(exc),
            raw_preview=raw[:_RAW_PREVIEW_LIMIT],
        )
        raise


def _load_json_object(raw: str) -> dict[str, Any]:
    """Parse a JSON object from raw LLM output."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text or "{}")
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match is None:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("extract response must be a JSON object")
    return parsed


def _normalize_category(value: str) -> str:
    """Normalize a fact category, including common LLM aliases."""
    normalized = str(value or "").strip().lower().replace("-", "_")
    normalized = re.sub(r"\s+", "_", normalized)
    return _CATEGORY_ALIASES.get(normalized, normalized)


def _clamp_float(value: Any, *, default: float) -> float:
    """Clamp one float into the 0..1 range."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(0.0, min(1.0, parsed))
