"""
JWT encoding/decoding utilities shared by every feature that needs to
issue or validate tokens (primarily `auth`, but `dependencies` in other
features decode access tokens too).

Two token types are supported, distinguished by a `type` claim so a
refresh token can never be replayed as an access token or vice versa:
  - "access"  — short-lived, sent on every authenticated request
  - "refresh" — long-lived, exchanged only at the refresh endpoint

Both also carry `jti` (a unique token ID) so individual tokens can be
revoked/blacklisted (e.g. in Redis) without invalidating every token a
user holds.
"""

import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from jose import ExpiredSignatureError, JWTError, jwt
from pydantic import BaseModel

from app.core.config import get_settings
from app.shared.exceptions import UnauthorizedException

settings = get_settings()


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenPayload(BaseModel):
    sub: str  # subject — the user's UUID as a string
    type: TokenType
    jti: str
    exp: datetime
    iat: datetime
    role: str | None = None


def _create_token(
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type.value,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str, role: str | None = None) -> str:
    """Create a short-lived access token for an authenticated user."""
    extra = {"role": role} if role else None
    return _create_token(
        subject,
        TokenType.ACCESS,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        extra,
    )


def create_refresh_token(subject: str) -> str:
    """Create a long-lived refresh token used only to mint new access tokens."""
    return _create_token(
        subject,
        TokenType.REFRESH,
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def create_password_reset_token(subject: str) -> str:
    """Create a short-lived, single-purpose password-reset token."""
    return _create_token(
        subject,
        TokenType.ACCESS,
        timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
        {"purpose": "password_reset"},
    )


def create_email_verification_token(subject: str) -> str:
    """Create a token used only to confirm ownership of an email address."""
    return _create_token(
        subject,
        TokenType.ACCESS,
        timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS),
        {"purpose": "email_verification"},
    )


def decode_token(token: str, expected_type: TokenType | None = None) -> TokenPayload:
    """Decode and validate a JWT, raising `UnauthorizedException` on any
    failure (expired, malformed, wrong signature, or wrong token type).

    Callers should never need to catch `jose` exceptions directly — this
    is the single translation point from "JWT library errors" to the
    application's own exception hierarchy.
    """
    try:
        raw = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except ExpiredSignatureError as exc:
        raise UnauthorizedException(
            "Token has expired.", error_code="TOKEN_EXPIRED"
        ) from exc
    except JWTError as exc:
        raise UnauthorizedException(
            "Could not validate token.", error_code="TOKEN_INVALID"
        ) from exc

    try:
        payload = TokenPayload(**raw)
    except Exception as exc:
        raise UnauthorizedException(
            "Token payload is malformed.", error_code="TOKEN_INVALID"
        ) from exc

    if expected_type is not None and payload.type != expected_type:
        raise UnauthorizedException(
            f"Expected a {expected_type.value} token.", error_code="TOKEN_TYPE_MISMATCH"
        )

    return payload
