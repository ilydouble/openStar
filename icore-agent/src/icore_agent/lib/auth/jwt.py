"""Small HS256 JWT helper used by iCore backend and gateway authentication."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any


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
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = ".".join(
        [_json_b64url(header), _json_b64url(claims)]
    )
    signature = _sign(signing_input, secret)
    return f"{signing_input}.{signature}"


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

    parts = token.split(".")
    if len(parts) != 3:
        raise JWTValidationError("token must have three JWT segments")

    header_segment, payload_segment, signature = parts
    signing_input = f"{header_segment}.{payload_segment}"
    expected = _sign(signing_input, secret)
    if not hmac.compare_digest(signature, expected):
        raise JWTValidationError("invalid token signature")

    header = _decode_json_segment(header_segment)
    if header.get("alg") != "HS256":
        raise JWTValidationError("unsupported token algorithm")

    claims = _decode_json_segment(payload_segment)
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


def _json_b64url(payload: Mapping[str, Any]) -> str:
    """Serialize a JSON object into an unpadded base64url segment."""
    raw = json.dumps(payload, separators=(",", ":"),
                     sort_keys=True).encode("utf-8")
    return _b64url_encode(raw)


def _decode_json_segment(segment: str) -> dict[str, Any]:
    """Decode one base64url JWT segment into a JSON object."""
    try:
        payload = json.loads(_b64url_decode(segment))
    except (json.JSONDecodeError, ValueError) as exc:
        raise JWTValidationError("token payload is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise JWTValidationError("token payload must be a JSON object")
    return payload


def _sign(signing_input: str, secret: str) -> str:
    """Return the unpadded base64url HMAC-SHA256 signature."""
    digest = hmac.new(secret.encode("utf-8"),
                      signing_input.encode("ascii"), hashlib.sha256)
    return _b64url_encode(digest.digest())


def _b64url_encode(raw: bytes) -> str:
    """Encode bytes as unpadded base64url text."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> str:
    """Decode unpadded base64url text into UTF-8 text."""
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(f"{segment}{padding}").decode("utf-8")
