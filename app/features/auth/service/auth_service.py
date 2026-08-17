"""
Authentication service — orchestrates the register/login/refresh/logout,
password-reset, change-password, and email-verification flows on top of
the auth repositories and the shared/local JWT/password utilities.

Route handlers stay thin (see `api/auth_router.py`); every rule about
*how* a user gets authenticated or how their credentials get changed —
password verification, refresh-token rotation and revocation, default
role assignment, purpose-token validation — lives here.
"""
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.features.auth.exceptions.auth_exceptions import (
    InvalidCredentialsException,
    InvalidPurposeTokenException,  

    InvalidRefreshTokenException,
)
from app.features.auth.models.user import User, UserRole
from app.features.auth.repository.refresh_token_repository import RefreshTokenRepository
from app.features.auth.repository.role_repository import RoleRepository
from app.features.auth.repository.user_repository import UserRepository
from app.features.auth.schemas.login import LoginRequest
from app.features.auth.schemas.register import RegisterRequest
from app.features.auth.schemas.token import TokenResponse
from app.features.auth.utils.email_sender import send_password_reset_email, send_verification_email
from app.features.auth.utils.token_utils import (
    EMAIL_VERIFICATION_PURPOSE,
    PASSWORD_RESET_PURPOSE,
    create_email_verification_token,
    create_password_reset_token,
    decode_purpose_token,
)
from app.shared.exceptions import ConflictException, ForbiddenException
from app.shared.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

logger = structlog.get_logger(__name__)
settings = get_settings()

# Every self-registered user starts with this role. Seeded on first use
# rather than via a fixture/migration so this phase doesn't depend on a
# separate role-seeding step.
DEFAULT_ROLE_NAME = "employee"
DEFAULT_ROLE_DESCRIPTION = "Standard employee-level access."


class AuthService:
    """Coordinates the auth repositories, shared security utilities, and
    local purpose-token/email helpers to implement every auth use case.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.roles = RoleRepository(db)
        self.refresh_tokens = RefreshTokenRepository(db)

    # ------------------------------------------------------------------ #
    # Register
    # ------------------------------------------------------------------ #

    async def register(self, payload: RegisterRequest, background_tasks: BackgroundTasks) -> User:
        """Create a new user account with the default role and send a
        verification email in the background.

        Checks for an existing email up front for a clean error message;
        `UserRepository.create` still guards against a concurrent
        duplicate insert via the database's unique constraint.
        """
        existing = await self.users.get_by_email(payload.email)
        if existing is not None:
            raise ConflictException(
                "A user with this email address already exists.",
                error_code="USER_ALREADY_EXISTS",
            )

        hashed_password = hash_password(payload.password)
        user = await self.users.create(email=payload.email, hashed_password=hashed_password)
        await self._assign_default_role(user)

        token = create_email_verification_token(str(user.id))
        print("\n" + "=" * 80)
        print("EMAIL VERIFICATION TOKEN:")
        print(token)
        print("=" * 80 + "\n")
        background_tasks.add_task(send_verification_email, to_email=user.email, token=token)

        logger.info("user_registered", user_id=str(user.id), email=user.email)
        return user

    async def _assign_default_role(self, user: User) -> None:
        """Grant `DEFAULT_ROLE_NAME` to a newly registered user, creating
        the role itself the first time it's needed.
        """
        role = await self.roles.get_by_name(DEFAULT_ROLE_NAME)
        if role is None:
            role = await self.roles.create(
                name=DEFAULT_ROLE_NAME, description=DEFAULT_ROLE_DESCRIPTION
            )
        self.db.add(UserRole(user_id=user.id, role_id=role.id))
        await self.db.flush()

    # ------------------------------------------------------------------ #
    # Login
    # ------------------------------------------------------------------ #

    async def login(self, payload: LoginRequest) -> TokenResponse:
        """Verify credentials and issue a new access/refresh token pair."""
        user = await self.users.get_by_email(payload.email)
        if user is None or not verify_password(payload.password, user.hashed_password):
            logger.warning("login_failed_invalid_credentials", email=payload.email)
            raise InvalidCredentialsException()

        if not user.is_active:
            raise ForbiddenException(
                "This user account has been deactivated.", error_code="USER_INACTIVE"
            )

        tokens = await self._issue_tokens(user)
        logger.info("user_logged_in", user_id=str(user.id))
        return tokens

    # ------------------------------------------------------------------ #
    # Refresh
    # ------------------------------------------------------------------ #

    async def refresh(self, refresh_token: str) -> TokenResponse:
        """Rotate a refresh token: validate it, revoke it, and issue a
        brand-new access/refresh token pair.

        Rotating on every use (rather than reusing the same refresh
        token) means a stolen-but-unused token is invalidated the next
        time the legitimate client refreshes.
        """
        decode_token(refresh_token, expected_type=TokenType.REFRESH)

        stored = await self.refresh_tokens.get_by_token(refresh_token)
        if stored is None or stored.revoked:
            raise InvalidRefreshTokenException()

        if stored.expires_at < datetime.now(timezone.utc):
            raise InvalidRefreshTokenException("Refresh token has expired.")

        user = await self.users.get_by_id(stored.user_id)
        if user is None or not user.is_active:
            raise InvalidRefreshTokenException()

        await self.refresh_tokens.revoke(refresh_token)
        tokens = await self._issue_tokens(user)
        logger.info("refresh_token_rotated", user_id=str(user.id))
        return tokens

    # ------------------------------------------------------------------ #
    # Logout
    # ------------------------------------------------------------------ #

    async def logout(self, refresh_token: str) -> None:
        """Revoke a single refresh token, ending that session.

        Only the targeted refresh token is revoked — other active
        sessions for the same user are left untouched, matching a
        single-device logout rather than a global sign-out.
        """
        stored = await self.refresh_tokens.get_by_token(refresh_token)
        if stored is None:
            raise InvalidRefreshTokenException()

        if not stored.revoked:
            await self.refresh_tokens.revoke(refresh_token)

        logger.info("user_logged_out", user_id=str(stored.user_id))

    # ------------------------------------------------------------------ #
    # Change password
    # ------------------------------------------------------------------ #

    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> None:
        """Change the authenticated user's password after verifying their
        current one, then revoke every other active session.
        """
        if not verify_password(current_password, user.hashed_password):
            raise InvalidCredentialsException()

        user.hashed_password = hash_password(new_password)
        await self.refresh_tokens.revoke_all_for_user(user.id)
        await self.db.flush()

        logger.info("password_changed", user_id=str(user.id))

    # ------------------------------------------------------------------ #
    # Forgot password / reset password
    # ------------------------------------------------------------------ #

    async def request_password_reset(
        self, email: str, background_tasks: BackgroundTasks
    ) -> None:
        """Send a password-reset email if the address belongs to an
        account.

        Always returns successfully regardless of whether the email
        exists — a differing response here would let an attacker
        enumerate registered accounts. The user only learns the outcome
        by checking their inbox.
        """
        user = await self.users.get_by_email(email)
        if user is None:
            logger.info("password_reset_requested_unknown_email", email=email)
            return

        token = create_password_reset_token(str(user.id))
        background_tasks.add_task(send_password_reset_email, to_email=user.email, token=token)
        logger.info("password_reset_requested", user_id=str(user.id))

    async def reset_password(self, token: str, new_password: str) -> None:
        """Complete a password reset using a token issued by
        `request_password_reset`, then revoke every active session.
        """
        user_id = decode_purpose_token(token, expected_purpose=PASSWORD_RESET_PURPOSE)

        user = await self.users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise InvalidPurposeTokenException()

        user.hashed_password = hash_password(new_password)
        await self.refresh_tokens.revoke_all_for_user(user.id)
        await self.db.flush()

        logger.info("password_reset_completed", user_id=str(user.id))

    # ------------------------------------------------------------------ #
    # Email verification
    # ------------------------------------------------------------------ #

    async def verify_email(self, token: str) -> None:
        """Mark a user's email as verified using a token issued at
        registration.
        """
        user_id = decode_purpose_token(token, expected_purpose=EMAIL_VERIFICATION_PURPOSE)

        user = await self.users.get_by_id(user_id)
        if user is None:
            raise InvalidPurposeTokenException()

        if not user.is_verified:
            user.is_verified = True
            await self.db.flush()

        logger.info("email_verified", user_id=str(user.id))

    # ------------------------------------------------------------------ #
    # Shared helpers
    # ------------------------------------------------------------------ #

    async def _issue_tokens(self, user: User) -> TokenResponse:
        """Mint a new access token (with the user's primary role claim)
        and refresh token, persist the refresh token, and return both.
        """
        primary_role = user.user_roles[0].role.name if user.user_roles else None

        access_token = create_access_token(str(user.id), role=primary_role)
        refresh_token = create_refresh_token(str(user.id))
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        await self.refresh_tokens.create(
            user_id=user.id, token=refresh_token, expires_at=expires_at
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )