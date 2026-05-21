"""Shared Authorization header helpers (Bearer token extraction)."""


def extract_bearer_token(authorization_header: str | None) -> str | None:
    """Return the bearer token substring, or None if the header is absent or malformed.

    RFC 7617 scheme name is matched case-insensitively so clients sending
    ``bearer <token>`` still authenticate.
    """
    if authorization_header is None:
        return None
    raw = authorization_header.strip()
    if len(raw) < 8:
        return None
    scheme, sep, rest = raw.partition(" ")
    if sep != " ":
        return None
    if scheme.lower() != "bearer":
        return None
    token = rest.strip()
    return token or None
