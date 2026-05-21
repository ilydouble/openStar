"""Plan upgrade schemas."""

from pydantic import BaseModel


class UpgradePlanRequest(BaseModel):
    plan: str  # "team" | "enterprise" | "byok"
    byok_api_key: str | None = None
    byok_api_base: str | None = None
    byok_model: str | None = None
