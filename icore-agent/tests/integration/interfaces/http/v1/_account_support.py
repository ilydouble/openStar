"""Account setup helpers for authenticated HTTP integration tests."""

from __future__ import annotations

import time
from uuid import uuid4

from tests.support.http import ASGISyncTestClient, api_data


def register_trial_direct(
    client: ASGISyncTestClient,
    email: str | None = None,
    name: str = "Trial User",
) -> dict:
    """Register a trial user after injecting a deterministic verification code."""
    from icore_agent.contexts.account.infrastructure.control_plane.json_store import (
        control_plane_store,
    )

    email = email or f"trial-{uuid4().hex[:8]}@example.com"
    code = "123456"
    with control_plane_store._lock:
        data = control_plane_store._load()
        data.setdefault("verification_codes", {})[email.lower()] = {
            "code": code,
            "expires_at": int(time.time()) + 600,
            "ip": "127.0.0.1",
            "timestamp": int(time.time()),
        }
        data.setdefault("ip_registrations", {}).pop("127.0.0.1", None)
        data.setdefault("ip_registrations", {}).pop("testclient", None)
        control_plane_store._save(data)

    response = client.post(
        "/api/v1/account/register-trial",
        json={"name": name, "email": email, "verification_code": code},
    )
    assert response.status_code == 200, response.json()
    return api_data(response)


def trial_headers(client: ASGISyncTestClient) -> dict[str, str]:
    """Return authorization headers for a newly registered trial user."""
    payload = register_trial_direct(client)
    return {"Authorization": f"Bearer {payload['access_token']}"}
