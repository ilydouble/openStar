"""Authentication and trial registration schemas."""

from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


class SendVerificationCodeRequest(BaseModel):
    email: EmailStr
    purpose: Literal["login", "register"] = "register"


class SendVerificationCodeResponse(BaseModel):
    success: bool
    message: str


class TrialRegistrationRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    email: EmailStr
    verification_code: str = Field(..., min_length=6, max_length=6)


class UserProfilePayload(BaseModel):
    id: str
    name: str
    email: EmailStr
    plan: str
    plan_label: str
    organization_id: str
    organization_name: str
    roles: list[str]
    byok: dict[str, Any]
    usage: dict[str, Any]
    created_at: int
    updated_at: int


class TrialRegistrationResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfilePayload


class EmailLoginRequest(BaseModel):
    """邮箱 + 验证码登录（已注册用户）"""

    email: EmailStr
    verification_code: str = Field(..., min_length=6, max_length=6)


class EmailLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfilePayload
