"""Authentication and trial registration handlers."""

from fastapi import Depends, HTTPException, Request

from icore_agent.application.account import AccountService

from ...dependencies import get_account_service
from ..schemas.auth import (
    EmailLoginRequest,
    EmailLoginResponse,
    SendVerificationCodeRequest,
    SendVerificationCodeResponse,
    TrialRegistrationRequest,
    TrialRegistrationResponse,
)


async def send_verification_code(
    req: SendVerificationCodeRequest,
    request: Request,
    service: AccountService = Depends(get_account_service),
) -> SendVerificationCodeResponse:
    """发送邮箱验证码（同一 IP 24 小时内最多发送 3 次）"""
    client_ip = request.client.host if request.client else "unknown"

    success, message = service.send_verification_code(req.email, client_ip)
    if not success:
        raise HTTPException(status_code=429, detail=message)

    return SendVerificationCodeResponse(success=True, message=message)


async def email_login(
    req: EmailLoginRequest,
    service: AccountService = Depends(get_account_service),
) -> EmailLoginResponse:
    """邮箱 + 验证码登录（已注册用户，无 IP 限流）"""
    try:
        user, token = service.login_with_email_code(
            req.email, req.verification_code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return EmailLoginResponse(access_token=token, user=user)


async def register_trial(
    req: TrialRegistrationRequest,
    request: Request,
    service: AccountService = Depends(get_account_service),
) -> TrialRegistrationResponse:
    """注册试用账号（需要邮箱验证码 + IP 限流：同一 IP 24 小时内只能注册 1 次）"""
    client_ip = request.client.host if request.client else "unknown"

    try:
        user, token = service.register_trial(
            name=req.name,
            email=req.email,
            verification_code=req.verification_code,
            client_ip=client_ip,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    return TrialRegistrationResponse(access_token=token, user=user)
