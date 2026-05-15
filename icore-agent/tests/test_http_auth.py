"""Tests for shared Authorization Bearer parsing."""

from __future__ import annotations

from icore_agent.api.http_auth import extract_bearer_token


def test_extract_bearer_token_accepts_lowercase_scheme():
    assert extract_bearer_token("bearer abc.xyz") == "abc.xyz"


def test_extract_bearer_token_accepts_mixed_case_scheme():
    assert extract_bearer_token("BeAreR secret-token") == "secret-token"


def test_extract_bearer_returns_none_when_missing_scheme():
    assert extract_bearer_token("Basic xxx") is None
    assert extract_bearer_token("") is None

