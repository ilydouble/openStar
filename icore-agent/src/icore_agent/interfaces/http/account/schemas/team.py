"""Team management schemas."""

from pydantic import BaseModel, EmailStr, Field


class OrganizationRenameRequest(BaseModel):
    organization_name: str = Field(..., min_length=1, max_length=120)


class TeamMemberRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    email: EmailStr
    role: str = Field(default="viewer", max_length=40)


class KnowledgeScopeRequest(BaseModel):
    scope: str = Field(..., pattern="^(private|organization)$")
