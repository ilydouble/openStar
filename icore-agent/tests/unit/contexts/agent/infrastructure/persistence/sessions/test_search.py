"""Tests for agent session persistence search policy."""

from icore_agent.contexts.agent.infrastructure.persistence.sessions import (
    repository as search_repo,
)


def test_session_search_sql_uses_english_fts_and_trigram_ranking() -> None:
    """Search SQL should combine English FTS with trigram and title ranking."""
    assert search_repo._SEARCH_LANG == "english"
    assert search_repo._TITLE_RANK_BOOST == 2.0
    assert "plainto_tsquery('english'" in search_repo._SESSION_SEARCH_QUERY_CTE
    assert "similarity(" in search_repo._SESSION_SEARCH_TITLE_SCORE_SQL
    assert "ILIKE '%' || q.raw_text || '%'" in search_repo._SESSION_SEARCH_MATCH_SQL
    assert f"* {search_repo._TITLE_RANK_BOOST}" in search_repo._SESSION_SEARCH_RANK_SQL
