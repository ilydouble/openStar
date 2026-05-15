from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from icore_agent.lib.auth.jwt import JWTValidationError, sign_access_token, verify_access_token


def test_sign_access_token_returns_hs256_claims():
    token = sign_access_token(
        user={"id": "user-1", "roles": ["owner", "admin"]},
        secret="test-secret",
        issuer="icore-agent",
        audience="icore-gateway",
        ttl_seconds=3600,
        now=datetime(2026, 5, 15, 8, 0, tzinfo=UTC),
    )

    claims = verify_access_token(
        token,
        secret="test-secret",
        issuer="icore-agent",
        audience="icore-gateway",
        now=datetime(2026, 5, 15, 8, 30, tzinfo=UTC),
    )

    assert token.count(".") == 2
    assert claims["sub"] == "user-1"
    assert claims["roles"] == ["owner", "admin"]
    assert claims["iss"] == "icore-agent"
    assert claims["aud"] == "icore-gateway"
    assert claims["iat"] == int(
        datetime(2026, 5, 15, 8, 0, tzinfo=UTC).timestamp())
    assert claims["exp"] == int(
        datetime(2026, 5, 15, 9, 0, tzinfo=UTC).timestamp()
    )


def test_verify_access_token_rejects_tampered_signature():
    token = sign_access_token(
        user={"id": "user-1", "roles": ["owner"]},
        secret="test-secret",
        issuer="icore-agent",
        audience="icore-gateway",
        ttl_seconds=3600,
        now=datetime(2026, 5, 15, 8, 0, tzinfo=UTC),
    )
    header, payload, _signature = token.split(".")

    with pytest.raises(JWTValidationError, match="signature"):
        verify_access_token(
            f"{header}.{payload}.bad",
            secret="test-secret",
            issuer="icore-agent",
            audience="icore-gateway",
            now=datetime(2026, 5, 15, 8, 30, tzinfo=UTC),
        )


def test_verify_access_token_rejects_expired_token():
    token = sign_access_token(
        user={"id": "user-1", "roles": ["owner"]},
        secret="test-secret",
        issuer="icore-agent",
        audience="icore-gateway",
        ttl_seconds=60,
        now=datetime(2026, 5, 15, 8, 0, tzinfo=UTC),
    )

    with pytest.raises(JWTValidationError, match="expired"):
        verify_access_token(
            token,
            secret="test-secret",
            issuer="icore-agent",
            audience="icore-gateway",
            now=datetime(2026, 5, 15, 8, 0, tzinfo=UTC) +
            timedelta(seconds=61),
        )
