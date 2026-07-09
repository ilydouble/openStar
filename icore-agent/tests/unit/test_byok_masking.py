from icore_agent.contexts.account.application.byok import resolve_api_key_for_update
from icore_agent.contexts.account.interfaces.http.v1.users.serializers import (
    mask_api_key,
    serialize_byok,
)


def test_mask_api_key_returns_empty_for_blank_value():
    assert mask_api_key("") == ""
    assert mask_api_key(None) == ""


def test_mask_api_key_masks_standard_keys_with_last_four_chars():
    assert mask_api_key("sk-live-abc123xyz789") == "sk-****z789"
    assert mask_api_key("demo-key") == "****-key"


def test_mask_api_key_short_keys_are_fully_redacted():
    assert mask_api_key("abc") == "****"


def test_serialize_byok_masks_api_key_only():
    payload = serialize_byok(
        {
            "enabled": True,
            "api_key": "sk-secret-value-1234",
            "api_base": "https://relay.example.com",
            "model": "openai/gpt-4o-mini",
        },
    )

    assert payload["enabled"] is True
    assert payload["api_key"] == "sk-****1234"
    assert payload["api_base"] == "https://relay.example.com"
    assert payload["model"] == "openai/gpt-4o-mini"


def test_resolve_api_key_for_update_preserves_existing_when_omitted_or_masked():
    existing = "sk-secret-value-1234"

    assert resolve_api_key_for_update("", existing) == existing
    assert resolve_api_key_for_update("sk-****1234", existing) == existing


def test_resolve_api_key_for_update_replaces_existing_when_new_key_provided():
    assert resolve_api_key_for_update(
        "sk-new-key", "sk-old-key") == "sk-new-key"
