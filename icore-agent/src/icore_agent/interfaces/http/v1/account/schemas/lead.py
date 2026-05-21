"""Lead capture schemas."""

from pydantic import BaseModel, EmailStr, Field


class LeadCaptureRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    company: str = Field(default="", max_length=160)
    team_size: str = Field(default="", max_length=80)
    use_case: str = Field(default="", max_length=2000)
    needs_byok: bool = False
    needs_private_deploy: bool = False
    source: str = Field(default="landing", max_length=80)
    intent: str = Field(
        default="demo", pattern="^(demo|enterprise|upgrade-team|upgrade-enterprise)$")
