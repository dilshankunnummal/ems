"""
Purpose-scoped token helpers for the password-reset and email-verification
flows.

These are short-lived, single-purpose JWTs kept deliberately separate from
the access/refresh token machinery in `app.shared.security`: they carry a
`purpose` claim instead of a `type` claim, so a stolen reset/verification
link can never be replayed as an API access token, and an access token can
never be replayed as a reset link. Kept local to the auth feature since
nothing outside auth needs them.
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt

from app.core.config import get_settings
from app.features.auth.exceptions.auth_exceptions import InvalidPurposeTokenException

settings = get_settings()

PASSWORD_RESET_PURPOSE = "password_reset"
EMAIL_VERIFICATION_PURPOSE = "email_verification"

PASSWORD_RESET_EXPIRE_MINUTES = 30
EMAIL_VERIFICATION_EXPIRE_HOURS = 24


def _create_purpose_token(user_id: str, purpose: str, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "purpose": purpose,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_password_reset_token(user_id: str) -> str:
    """Mint a 30-minute password-reset token for the given user id."""
    return _create_purpose_token(
        user_id, PASSWORD_RESET_PURPOSE, timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES)
    )


def create_email_verification_token(user_id: str) -> str:
    """Mint a 24-hour email-verification token for the given user id."""
    return _create_purpose_token(
        user_id, EMAIL_VERIFICATION_PURPOSE, timedelta(hours=EMAIL_VERIFICATION_EXPIRE_HOURS)
    )


def decode_purpose_token(token: str, expected_purpose: str) -> UUID:
    """Decode a purpose-scoped token and return the embedded user id.

    Raises `InvalidPurposeTokenException` for every failure mode — bad
    signature, expiry, or a purpose that doesn't match what the caller
    expected. Callers never need to distinguish these: the client-facing
    behaviour (the link is dead, request a new one) is identical either
    way, and returning finer-grained errors here would leak whether a
    given token *almost* worked.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise InvalidPurposeTokenException() from exc

    if payload.get("purpose") != expected_purpose:
        raise InvalidPurposeTokenException()

    subject = payload.get("sub")
    if not subject:
        raise InvalidPurposeTokenException()

    try:
        return UUID(subject)
    except ValueError as exc:
        raise InvalidPurposeTokenException() from exc