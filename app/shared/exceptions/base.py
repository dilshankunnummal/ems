"""
Base application exception hierarchy.

Every feature raises one of these instead of a raw HTTPException, so
the global exception handler (app/shared/middleware/exception_handler.py)
can translate them into a single consistent JSON error contract.
"""
from typing import Any


class AppException(Exception):
    """Base class for all application-level exceptions."""

    status_code: int = 500
    error_code: str = "INTERNAL_SERVER_ERROR"

    def __init__(
        self,
        message: str = "An unexpected error occurred.",
        *,
        status_code: int | None = None,
        error_code: str | None = None,
        details: Any = None,
    ) -> None:
        self.message = message
        self.status_code = status_code or self.status_code
        self.error_code = error_code or self.error_code
        self.details = details
        super().__init__(message)


class BadRequestException(AppException):
    status_code = 400
    error_code = "BAD_REQUEST"


class ValidationException(AppException):
    status_code = 422
    error_code = "VALIDATION_ERROR"


class UnauthorizedException(AppException):
    status_code = 401
    error_code = "UNAUTHORIZED"


class ForbiddenException(AppException):
    status_code = 403
    error_code = "FORBIDDEN"


class NotFoundException(AppException):
    status_code = 404
    error_code = "NOT_FOUND"


class ConflictException(AppException):
    status_code = 409
    error_code = "CONFLICT"


class TooManyRequestsException(AppException):
    status_code = 429
    error_code = "TOO_MANY_REQUESTS"


class InternalServerException(AppException):
    status_code = 500
    error_code = "INTERNAL_SERVER_ERROR"
