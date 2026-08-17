"""
Authentication API routes.

Every endpoint in this router is now fully wired to `AuthService` — no
placeholder 501s remain. Handlers stay thin: request validation,
dependency resolution, and response-contract shaping only.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.features.auth.dependencies.auth_dependencies import current_active_user
from app.features.auth.models.user import User
from app.features.auth.schemas.login import LoginRequest
from app.features.auth.schemas.password import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.features.auth.schemas.register import RegisterRequest
from app.features.auth.schemas.token import RefreshTokenRequest, TokenResponse
from app.features.auth.schemas.user import UserResponse
from app.features.auth.service.auth_service import AuthService
from app.shared.responses.envelope import ResponseEnvelope

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=ResponseEnvelope[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    payload: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[UserResponse]:
    user = await AuthService(db).register(payload, background_tasks)
    return ResponseEnvelope(
        data=UserResponse.model_validate(user),
        message="Account created successfully. Please check your email to verify your account.",
    )


@router.post(
    "/login",
    response_model=ResponseEnvelope[TokenResponse],
    summary="Authenticate and obtain an access/refresh token pair",
)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[TokenResponse]:
    tokens = await AuthService(db).login(payload)
    return ResponseEnvelope(data=tokens, message="Login successful.")


@router.post(
    "/logout",
    response_model=ResponseEnvelope[None],
    summary="Revoke the caller's refresh token",
)
async def logout(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_active_user),
) -> ResponseEnvelope[None]:
    await AuthService(db).logout(payload.refresh_token)
    return ResponseEnvelope(message="Logged out successfully.")


@router.post(
    "/refresh",
    response_model=ResponseEnvelope[TokenResponse],
    summary="Exchange a refresh token for a new access/refresh token pair",
)
async def refresh(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[TokenResponse]:
    tokens = await AuthService(db).refresh(payload.refresh_token)
    return ResponseEnvelope(data=tokens, message="Token refreshed successfully.")


@router.post(
    "/change-password",
    response_model=ResponseEnvelope[None],
    summary="Change the authenticated user's password",
)
async def change_password(
    payload: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_active_user),
) -> ResponseEnvelope[None]:
    await AuthService(db).change_password(
        user, payload.current_password, payload.new_password
    )
    return ResponseEnvelope(message="Password changed successfully. Please log in again.")


@router.post(
    "/forgot-password",
    response_model=ResponseEnvelope[None],
    summary="Request a password-reset email",
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[None]:
    await AuthService(db).request_password_reset(payload.email, background_tasks)
    return ResponseEnvelope(
        message="If an account exists for that email, a password-reset link has been sent."
    )


@router.post(
    "/reset-password",
    response_model=ResponseEnvelope[None],
    summary="Reset a password using a password-reset token",
)
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[None]:
    await AuthService(db).reset_password(payload.token, payload.new_password)
    return ResponseEnvelope(message="Password reset successfully. You can now log in.")


@router.get(
    "/me",
    response_model=ResponseEnvelope[UserResponse],
    summary="Get the authenticated user's profile",
)
async def get_me(
    user: User = Depends(current_active_user),
) -> ResponseEnvelope[UserResponse]:
    return ResponseEnvelope(data=UserResponse.model_validate(user))


@router.get(
    "/verify-email",
    response_model=ResponseEnvelope[None],
    summary="Verify a user's email address using an email-verification token",
)
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[None]:
    await AuthService(db).verify_email(token)
    return ResponseEnvelope(message="Email verified successfully.")