"""Tests for chat session full-text search."""

from __future__ import annotations

from icore_agent.application.chat.service import ChatHistoryService


def test_search_user_sessions_empty_query_returns_no_results() -> None:
    """Blank search text should short-circuit without hitting the database."""
    service = ChatHistoryService()
    payload = service.search_user_sessions("user-1", query="   ")
    assert payload == {
        "query": "",
        "sessions": [],
        "total": 0,
        "limit": 20,
        "offset": 0,
    }


def test_search_user_sessions_clamps_pagination() -> None:
    """Search pagination bounds should mirror the list endpoint."""
    service = ChatHistoryService()
    payload = service.search_user_sessions(
        "missing-user",
        query="hello",
        limit=500,
        offset=-3,
    )
    assert payload["limit"] == 100
    assert payload["offset"] == 0
    assert payload["query"] == "hello"
    assert payload["sessions"] == []
    assert payload["total"] == 0
