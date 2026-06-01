"""Scoring, caps, and supersession rules for user memory."""

from __future__ import annotations

import math
import re
from typing import Any

from icore_agent.application.usage.policy import current_timestamp
from icore_agent.domain.memory import TurnMemoryContext, UserMemoryFact

PROFILE_MAX_KEYS = 8
PROFILE_MAX_VALUE_LEN = 80
FACT_MAX_VALUE_LEN = 200
ACTIVE_FACT_CAP = 30
INJECT_FACT_LIMIT = 5
RELEVANCE_THRESHOLD = 0.25
PROMPT_CHAR_BUDGET = 2000


def session_has_extractable_content(
    session_summary: str | None,
    recent_messages: list[dict[str, str]],
) -> bool:
    """Return whether a session slice contains enough content to extract memory."""
    if str(session_summary or "").strip():
        return True
    return len(filter_messages_for_extraction(recent_messages)) > 0


_ALLOWED_PROFILE_KEYS = frozenset({
    "language",
    "tone",
    "role",
    "domain",
    "output_format",
    "timezone",
    "industry",
    "team_size",
})

_PROFILE_KEY_ALIASES = {
    "job_title": "role",
    "job": "role",
    "title": "role",
    "communication_style": "tone",
    "work_domain": "domain",
}

_CATEGORY_DECAY_LAMBDA = {
    "preference": 0.004,
    "work_context": 0.008,
    "goal": 0.012,
    "constraint": 0.006,
    "personal": 0.023,
}

_HINT_CATEGORY_BOOST = {
    "research": {"work_context", "goal"},
    "data": {"constraint", "work_context"},
    "knowledge": {"work_context", "constraint"},
    "code": {"work_context", "preference"},
    "image": {"personal", "work_context"},
    "chat": {"preference", "personal"},
}

# Canonical keys for category="personal" facts.
_PERSONAL_FACT_KEYS = frozenset({
    "name",
    "age",
    "location",
    "pronouns",
    "birthday",
    "nationality",
})

_FACT_KEY_ALIASES = {
    "full_name": "name",
    "preferred_name": "name",
    "display_name": "name",
    "first_name": "name",
    "given_name": "name",
    "user_name": "name",
    "years_old": "age",
    "user_age": "age",
    "country": "location",
    "region": "location",
    "city": "location",
    "home_country": "location",
    "country_of_residence": "location",
    "residence": "location",
    "geo": "location",
    "locale": "location",
    "personal_info": "name",
}

_ATTACHMENT_PLACEHOLDER_PATTERNS = (
    re.compile(r"please answer based on", re.I),
    re.compile(r"uploaded (the )?(images|files|documents)", re.I),
    re.compile(r"根据我上传", re.I),
)


def normalize_profile_updates(updates: dict[str, Any]) -> dict[str, str]:
    """Return bounded profile updates limited to known stable keys."""
    normalized, _dropped = normalize_profile_updates_with_trace(updates)
    return normalized


def normalize_profile_updates_with_trace(
    updates: dict[str, Any],
) -> tuple[dict[str, str], list[str]]:
    """Return profile updates and keys that were dropped by policy."""
    normalized: dict[str, str] = {}
    dropped: list[str] = []
    for raw_key, raw_value in dict(updates or {}).items():
        key = str(raw_key).strip().lower()
        key = _PROFILE_KEY_ALIASES.get(key, key)
        if key not in _ALLOWED_PROFILE_KEYS:
            dropped.append(key)
            continue
        value = str(raw_value).strip()
        if not value:
            dropped.append(key)
            continue
        normalized[key] = value[:PROFILE_MAX_VALUE_LEN]
        if len(normalized) >= PROFILE_MAX_KEYS:
            break
    return normalized, dropped


def merge_profile(
    existing: dict[str, Any],
    updates: dict[str, Any],
) -> dict[str, str]:
    """Merge normalized profile updates onto an existing profile."""
    merged = {
        str(key): str(value)[:PROFILE_MAX_VALUE_LEN]
        for key, value in dict(existing or {}).items()
        if str(key).strip()
    }
    merged.update(normalize_profile_updates(updates))
    return {
        key: merged[key]
        for key in list(merged.keys())[:PROFILE_MAX_KEYS]
    }


def normalize_fact_value(value: str) -> str:
    """Trim and cap one fact value."""
    return str(value or "").strip()[:FACT_MAX_VALUE_LEN]


def normalize_fact_key(raw_key: str) -> str:
    """Normalize a fact key to canonical snake_case."""
    normalized = re.sub(r"[^a-z0-9_]+", "_",
                        str(raw_key or "").strip().lower())
    normalized = normalized.strip("_")[:64]
    return _FACT_KEY_ALIASES.get(normalized, normalized)


def normalize_personal_fact_key(raw_key: str) -> str | None:
    """Return a canonical personal fact key when the raw key maps to one."""
    canonical = normalize_fact_key(raw_key)
    if canonical in _PERSONAL_FACT_KEYS:
        return canonical
    return None


def personal_facts_from_profile_updates(
    updates: dict[str, Any],
) -> list[tuple[str, str]]:
    """Promote personal fields placed in profile_updates into personal fact slots."""
    promoted: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw_key, raw_value in dict(updates or {}).items():
        profile_key = str(raw_key).strip().lower()
        profile_key = _PROFILE_KEY_ALIASES.get(profile_key, profile_key)
        if profile_key in _ALLOWED_PROFILE_KEYS:
            continue
        canonical = normalize_personal_fact_key(str(raw_key))
        if canonical is None or canonical in seen:
            continue
        value = normalize_fact_value(str(raw_value))
        if not value:
            continue
        promoted.append((canonical, value))
        seen.add(canonical)
    return promoted


def is_attachment_placeholder(text: str) -> bool:
    """Return whether a message is an attachment-only placeholder."""
    normalized = str(text or "").strip()
    if not normalized:
        return True
    return any(pattern.search(normalized) for pattern in _ATTACHMENT_PLACEHOLDER_PATTERNS)


def filter_messages_for_extraction(
    messages: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Return user/assistant messages suitable for memory extraction."""
    filtered: list[dict[str, str]] = []
    for message in messages:
        role = str(message.get("role") or "").strip().lower()
        content = str(message.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        if is_attachment_placeholder(content):
            continue
        filtered.append({"role": role, "content": content})
    return filtered[-8:]


def recency_score(fact: UserMemoryFact, *, now: int | None = None) -> float:
    """Compute exponential recency from the last confirmation timestamp."""
    timestamp = now or current_timestamp()
    anchor = int(fact.last_confirmed_at or fact.created_at or timestamp)
    days = max((timestamp - anchor) / 86_400, 0.0)
    decay = _CATEGORY_DECAY_LAMBDA.get(fact.category, 0.01)
    return math.exp(-decay * days)


def turn_relevance_score(
    fact: UserMemoryFact,
    turn: TurnMemoryContext,
) -> float:
    """Estimate turn relevance using token overlap and hint category boosts."""
    haystack = " ".join(
        part for part in (
            turn.message,
            turn.session_summary or "",
            turn.agent_hint or "",
        )
        if part
    ).lower()
    tokens = {token for token in re.findall(
        r"[a-z0-9\u4e00-\u9fff]+", haystack) if len(token) > 2}
    fact_tokens = {
        token
        for token in re.findall(r"[a-z0-9\u4e00-\u9fff]+", fact.value.lower())
        if len(token) > 2
    }
    overlap = 0.0
    if tokens and fact_tokens:
        overlap = len(tokens & fact_tokens) / max(len(fact_tokens), 1)
    hint = str(turn.agent_hint or "").strip().lower()
    boost = 0.15 if hint and fact.category in _HINT_CATEGORY_BOOST.get(
        hint, set()) else 0.0
    return min(1.0, overlap + boost)


def score_fact(
    fact: UserMemoryFact,
    turn: TurnMemoryContext,
    *,
    now: int | None = None,
) -> float:
    """Return the composite injection score for one active fact."""
    timestamp = now or current_timestamp()
    source_boost = 0.05 if fact.source == "explicit" else 0.0
    access_boost = min(0.1, fact.access_count * 0.01)
    score = (
        0.35 * recency_score(fact, now=timestamp)
        + 0.25 * float(fact.salience)
        + 0.25 * turn_relevance_score(fact, turn)
        + 0.10 * access_boost
        + 0.05 * source_boost
    ) * float(fact.confidence)
    return round(score, 6)


def rank_facts_for_turn(
    facts: list[UserMemoryFact],
    turn: TurnMemoryContext,
    *,
    limit: int = INJECT_FACT_LIMIT,
) -> list[UserMemoryFact]:
    """Return the highest-scoring active facts for one turn."""
    scored = [
        (score_fact(fact, turn), fact)
        for fact in facts
        if fact.status == "active"
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    selected: list[UserMemoryFact] = []
    for relevance, fact in scored:
        if relevance < RELEVANCE_THRESHOLD:
            continue
        selected.append(fact)
        if len(selected) >= limit:
            break
    return selected


def should_supersede(
    existing: UserMemoryFact,
    candidate_source: str,
) -> bool:
    """Return whether a candidate should replace an active fact."""
    if candidate_source == "explicit" and existing.source != "explicit":
        return True
    if candidate_source == "inferred" and existing.source == "explicit":
        return False
    return True


def values_equivalent(left: str, right: str) -> bool:
    """Return whether two fact values are effectively the same."""
    return normalize_fact_value(left).casefold() == normalize_fact_value(right).casefold()


def build_user_memory_prompt(
    profile: dict[str, Any],
    facts: list[UserMemoryFact],
) -> str | None:
    """Build the bounded user-memory section for the orchestrator prompt."""
    profile_lines = [
        f"- {key}: {value}"
        for key, value in dict(profile or {}).items()
        if str(value).strip()
    ]
    fact_lines = [f"- {fact.value}" for fact in facts if fact.value.strip()]
    if not profile_lines and not fact_lines:
        return None

    parts: list[str] = []
    if profile_lines:
        parts.append("## About this user\n" + "\n".join(profile_lines))
    if fact_lines:
        parts.append("## Relevant context\n" + "\n".join(fact_lines))
    prompt = "\n\n".join(parts)
    return prompt[:PROMPT_CHAR_BUDGET]
