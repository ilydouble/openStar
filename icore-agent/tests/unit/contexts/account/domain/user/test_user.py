"""Tests for account-owned user domain models."""

from icore_agent.contexts.account.domain.user import AuthenticatedUser, UserProfile


def test_authenticated_user_is_built_from_user_profile() -> None:
    """Authenticated requests should carry a domain user context, not a dict."""
    profile = UserProfile(
        public_id="user-1",
        email="user@example.com",
        name="User One",
        plan="trial",
        plan_label="Trial",
        organization_id="org-1",
        organization_name="Org One",
        roles=["owner", "admin"],
        byok={"enabled": True, "model": "openai/gpt-4o-mini"},
        usage={"messages": 3},
        created_at=10,
        updated_at=20,
    )

    user = AuthenticatedUser.from_profile(profile)

    assert user.public_id == "user-1"
    assert user.roles == ("owner", "admin")
    assert user.byok["model"] == "openai/gpt-4o-mini"
    assert user.usage["messages"] == 3
