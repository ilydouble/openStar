from __future__ import annotations

from icore_agent.contexts.account.application.usage.policy import current_timestamp
from icore_agent.contexts.memory.application import policy
from icore_agent.contexts.memory.application.consolidation import parse_extract_response
from icore_agent.contexts.memory.domain import TurnMemoryContext, UserMemoryFact


def test_build_user_memory_prompt_is_bounded() -> None:
    """User memory prompt must stay within the configured character budget."""
    profile = {"tone": "concise", "role": "seller"}
    facts = [
        UserMemoryFact(
            user_id="u1",
            category="work_context",
            key="platform",
            value="Shopify",
            confidence=0.9,
            salience=0.8,
            last_confirmed_at=current_timestamp(),
        )
    ]
    prompt = policy.build_user_memory_prompt(profile, facts)
    assert prompt is not None
    assert "About this user" in prompt
    assert "Shopify" in prompt
    assert len(prompt) <= policy.PROMPT_CHAR_BUDGET


def test_session_has_extractable_content() -> None:
    """Session-end extraction should skip empty sessions."""
    assert policy.session_has_extractable_content("", []) is False
    assert policy.session_has_extractable_content(
        "User prefers concise answers",
        [],
    ) is True
    assert policy.session_has_extractable_content(
        "",
        [{"role": "user", "content": "I run a Shopify store."}],
    ) is True


def test_rank_facts_for_turn_prefers_relevant_fact() -> None:
    """Turn relevance should rank matching facts above unrelated ones."""
    now = current_timestamp()
    facts = [
        UserMemoryFact(
            user_id="u1",
            category="work_context",
            key="platform",
            value="Shopify store operations",
            confidence=0.9,
            salience=0.8,
            last_confirmed_at=now,
        ),
        UserMemoryFact(
            user_id="u1",
            category="personal",
            key="pet",
            value="Has a golden retriever",
            confidence=0.9,
            salience=0.8,
            last_confirmed_at=now,
        ),
    ]
    selected = policy.rank_facts_for_turn(
        facts,
        TurnMemoryContext(
            message="Help me optimize my Shopify checkout flow",
        ),
    )
    assert selected
    assert "Shopify" in selected[0].value


def test_parse_extract_response_rejects_invalid_categories() -> None:
    """Extraction parser should keep only allowed categories and keys."""
    result = parse_extract_response(
        """
        {
          "profile_updates": {"tone": "concise", "unknown_key": "ignore"},
          "candidates": [
            {
              "category": "document",
              "key": "file_name",
              "value": "secret.pdf",
              "source": "explicit",
              "confidence": 1.0,
              "salience": 1.0
            },
            {
              "category": "work_context",
              "key": "Primary Platform",
              "value": "Shopify",
              "source": "explicit",
              "confidence": 0.9,
              "salience": 0.8
            }
          ]
        }
        """
    )
    assert result.profile_updates == {"tone": "concise"}
    assert len(result.candidates) == 1
    assert result.candidates[0].key == "primary_platform"


def test_parse_extract_response_accepts_category_aliases() -> None:
    """Common LLM category aliases should map to allowed categories."""
    result = parse_extract_response(
        """
        {
          "profile_updates": {},
          "candidates": [
            {
              "category": "preferences",
              "key": "tone",
              "value": "concise replies",
              "source": "explicit",
              "confidence": 0.9,
              "salience": 0.8
            }
          ]
        }
        """
    )
    assert len(result.candidates) == 1
    assert result.candidates[0].category == "preference"


def test_parse_extract_response_accepts_personal_name_and_age() -> None:
    """Personal facts with canonical keys should be accepted from candidates."""
    result = parse_extract_response(
        """
        {
          "profile_updates": {"role": "engineer"},
          "candidates": [
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
            }
          ]
        }
        """
    )
    assert result.profile_updates == {"role": "engineer"}
    assert len(result.candidates) == 2
    by_key = {candidate.key: candidate for candidate in result.candidates}
    assert by_key["name"].value == "Alex"
    assert by_key["age"].value == "34"
    assert by_key["name"].category == "personal"


def test_parse_extract_response_promotes_personal_fields_from_profile_updates() -> None:
    """Name and age wrongly placed in profile_updates should become personal facts."""
    result = parse_extract_response(
        """
        {
          "profile_updates": {
            "role": "seller",
            "name": "Alex",
            "age": "34",
            "country": "US",
            "unknown_key": "ignore"
          },
          "candidates": []
        }
        """
    )
    assert result.profile_updates == {"role": "seller"}
    by_key = {candidate.key: candidate for candidate in result.candidates}
    assert by_key["name"].value == "Alex"
    assert by_key["age"].value == "34"
    assert by_key["location"].value == "US"
    assert all(candidate.category ==
               "personal" for candidate in result.candidates)


def test_parse_extract_response_normalizes_personal_fact_key_aliases() -> None:
    """Common personal key aliases should map to canonical fact keys."""
    result = parse_extract_response(
        """
        {
          "profile_updates": {},
          "candidates": [
            {
              "category": "personal_info",
              "key": "full_name",
              "value": "Alex Kim",
              "source": "explicit",
              "confidence": 0.9,
              "salience": 0.8
            }
          ]
        }
        """
    )
    assert len(result.candidates) == 1
    assert result.candidates[0].category == "personal"
    assert result.candidates[0].key == "name"
    assert result.candidates[0].value == "Alex Kim"


def test_normalize_profile_updates_with_trace_reports_dropped_keys() -> None:
    """Unknown profile keys should be reported for extraction diagnostics."""
    normalized, dropped = policy.normalize_profile_updates_with_trace(
        {"role": "Ops analyst"},
    )
    assert normalized == {"role": "Ops analyst"}
    assert dropped == []

    normalized, dropped = policy.normalize_profile_updates_with_trace(
        {"job_title": "Ops analyst"},
    )
    assert normalized == {"role": "Ops analyst"}
    assert dropped == []


def test_should_supersede_prefers_explicit_over_inferred() -> None:
    """Explicit facts should replace inferred facts for the same slot."""
    existing = UserMemoryFact(
        user_id="u1",
        category="work_context",
        key="platform",
        value="WooCommerce",
        source="inferred",
    )
    assert policy.should_supersede(existing, "explicit") is True
    assert policy.should_supersede(existing, "inferred") is True

    explicit = UserMemoryFact(
        user_id="u1",
        category="work_context",
        key="platform",
        value="Shopify",
        source="explicit",
    )
    assert policy.should_supersede(explicit, "inferred") is False
