"""
Auth-specific exception types.

Thin wrappers over the shared exception hierarchy so every authentication
failure mode gets a stable, descriptive `error_code` without each call
site repeating the same message/status boilerplate.
"""
from app.shared.exceptions import UnauthorizedException


class InvalidCredentialsException(UnauthorizedException):
    """Raised when an email/password combination does not match."""

    def __init__(self) -> None:
        super().__init__(
            "Incorrect email or password.",
            error_code="INVALID_CREDENTIALS",
        )


class InvalidRefreshTokenException(UnauthorizedException):
    """Raised when a refresh token is malformed, unknown, expired, or
    has already been revoked.
    """

    def __init__(
        self, message: str = "Refresh token is invalid or has been revoked."
    ) -> None:
        super().__init__(message, error_code="INVALID_REFRESH_TOKEN")


class InvalidPurposeTokenException(UnauthorizedException):
    """Raised when a password-reset or email-verification token is
    malformed, expired, or doesn't match the purpose it's being used for.
    """

    def __init__(
        self,
        message: str = "This link is invalid or has expired. Please request a new one.",
    ) -> None:
        super().__init__(message, error_code="INVALID_OR_EXPIRED_TOKEN")