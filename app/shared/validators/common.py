"""
Reusable validation functions shared across feature Pydantic schemas.

These are plain functions (not tied to any one model) so a schema in
`employee`, `auth`, or `documents` can all enforce the same password
strength rule, phone format, or file-extension whitelist without
duplicating the logic.
"""

import re
from pathlib import Path

from app.core.config import get_settings
from app.shared.exceptions import ValidationException

_PHONE_PATTERN = re.compile(r"^\+?[1-9]\d{7,14}$")
_PASSWORD_UPPER = re.compile(r"[A-Z]")
_PASSWORD_LOWER = re.compile(r"[a-z]")
_PASSWORD_DIGIT = re.compile(r"\d")
_PASSWORD_SPECIAL = re.compile(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]")


def validate_strong_password(password: str) -> str:
    """Enforce a minimum password policy: 8+ chars, upper, lower, digit,
    special character. Raises ValueError so it can be used directly as a
    Pydantic `field_validator`.
    """
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if not _PASSWORD_UPPER.search(password):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not _PASSWORD_LOWER.search(password):
        raise ValueError("Password must contain at least one lowercase letter.")
    if not _PASSWORD_DIGIT.search(password):
        raise ValueError("Password must contain at least one digit.")
    if not _PASSWORD_SPECIAL.search(password):
        raise ValueError("Password must contain at least one special character.")
    return password


def validate_phone_number(phone: str) -> str:
    """Validate an E.164-ish phone number. Raises ValueError for Pydantic."""
    cleaned = phone.strip().replace(" ", "").replace("-", "")
    if not _PHONE_PATTERN.match(cleaned):
        raise ValueError(
            "Phone number must be a valid international format, e.g. +14155552671."
        )
    return cleaned


def validate_file_extension(filename: str, allowed_extensions: list[str]) -> None:
    """Raise ValidationException if `filename`'s extension is not whitelisted.

    Used at the API layer for uploads (profile images, resumes, documents),
    not as a Pydantic field validator, since it needs access to the
    per-upload-type allowed-extensions list from settings.
    """
    ext = Path(filename).suffix.lower()
    if ext not in allowed_extensions:
        raise ValidationException(
            f"File type '{ext}' is not allowed. Allowed types: {', '.join(allowed_extensions)}.",
            error_code="INVALID_FILE_TYPE",
        )


def validate_file_size(size_bytes: int) -> None:
    """Raise ValidationException if an uploaded file exceeds the configured
    maximum size.
    """
    settings = get_settings()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if size_bytes > max_bytes:
        raise ValidationException(
            f"File exceeds the maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB} MB.",
            error_code="FILE_TOO_LARGE",
        )
