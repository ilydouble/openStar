"""Authentication and trial registration schemas."""

from pydantic import BaseModel, EmailStr, Field


class SendVerificationCodeRequest(BaseModel):
    email: EmailStr


class SendVerificationCodeResponse(BaseModel):
    success: bool
    message: str


class TrialRegistrationRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    email: EmailStr
    verification_code: str = Field(..., min_length=6, max_length=6)


class TrialRegistrationResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class EmailLoginRequest(BaseModel):
    """邮箱 + 验证码登录（已注册用户）"""

    email: EmailStr
    verification_code: str = Field(..., min_length=6, max_length=6)


class EmailLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict
