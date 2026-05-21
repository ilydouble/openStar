"""HS256 JWT helper used by iCore backend and gateway authentication."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt as pyjwt
from jwt import InvalidSignatureError, InvalidTokenError


class JWTValidationError(ValueError):
    """Raised when a bearer token fails JWT validation."""


def sign_access_token(
    *,
    user: Mapping[str, Any],
    secret: str,
    issuer: str,
    audience: str,
    ttl_seconds: int,
    now: datetime | None = None,
) -> str:
    """Sign an HS256 access token for the authenticated user."""
    subject = str(user.get("id") or "").strip()
    if not subject:
        raise ValueError("user id is required")
    if not secret:
        raise ValueError("jwt secret is required")

    issued_at_dt = now or datetime.now(UTC)
    issued_at = _timestamp(issued_at_dt)
    expires_at = _timestamp(
        issued_at_dt + timedelta(seconds=max(ttl_seconds, 1)))
    claims: dict[str, Any] = {
        "sub": subject,
        "roles": _normalize_roles(user.get("roles")),
        "iss": issuer,
        "aud": audience,
        "iat": issued_at,
        "exp": expires_at,
    }
    return pyjwt.encode(
        claims,
        secret,
        algorithm="HS256",
        headers={"typ": "JWT"},
    )


def verify_access_token(
    token: str,
    *,
    secret: str,
    issuer: str,
    audience: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate an HS256 access token and return its claims."""
    if not secret:
        raise JWTValidationError("jwt secret is required")

    try:
        claims = pyjwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={
                "require": ["sub", "roles", "iss", "aud", "iat", "exp"],
                "verify_exp": False,
                "verify_iss": False,
                "verify_aud": False,
            },
        )
    except InvalidSignatureError as exc:
        raise JWTValidationError("invalid token signature") from exc
    except InvalidTokenError as exc:
        raise JWTValidationError(str(exc) or "invalid token") from exc
    _validate_claims(claims, issuer=issuer, audience=audience, now=now)
    return claims


def _validate_claims(
    claims: dict[str, Any],
    *,
    issuer: str,
    audience: str,
    now: datetime | None,
) -> None:
    """Validate issuer, audience, subject, roles, and expiry claims."""
    if not isinstance(claims.get("sub"), str) or not claims["sub"].strip():
        raise JWTValidationError("subject claim is required")
    if claims.get("iss") != issuer:
        raise JWTValidationError("issuer claim is invalid")
    if claims.get("aud") != audience:
        raise JWTValidationError("audience claim is invalid")
    if not isinstance(claims.get("roles"), list) or any(
        not isinstance(role, str) for role in claims["roles"]
    ):
        raise JWTValidationError("roles claim is invalid")

    expires_at = claims.get("exp")
    if not isinstance(expires_at, int):
        raise JWTValidationError("expiration claim is required")
    if _timestamp(now or datetime.now(UTC)) >= expires_at:
        raise JWTValidationError("token expired")


def _normalize_roles(value: Any) -> list[str]:
    """Return a stable list of non-empty string roles."""
    if not isinstance(value, list):
        return []
    return [str(role).strip() for role in value if str(role).strip()]


def _timestamp(value: datetime) -> int:
    """Return a UTC Unix timestamp for naive or aware datetimes."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return int(value.timestamp())
