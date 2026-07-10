"""Tests for account-owned BYOK application policy."""

from icore_agent.contexts.account.application.byok import resolve_api_key_for_update


def test_resolve_api_key_for_update_preserves_existing_when_omitted_or_masked():
    existing = "sk-secret-value-1234"

    assert resolve_api_key_for_update("", existing) == existing
    assert resolve_api_key_for_update("sk-****1234", existing) == existing


def test_resolve_api_key_for_update_replaces_existing_when_new_key_provided():
    assert resolve_api_key_for_update(
        "sk-new-key", "sk-old-key") == "sk-new-key"
