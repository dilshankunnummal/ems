"""Request schemas for the change/forgot/reset password flows."""

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator

from app.shared.validators.common import validate_strong_password


class ChangePasswordRequest(BaseModel):
    """Payload for `POST /auth/change-password` (requires authentication)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _validate_new_password_strength(cls, value: str) -> str:
        return validate_strong_password(value)


class ForgotPasswordRequest(BaseModel):
    """Payload for `POST /auth/forgot-password`."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Payload for `POST /auth/reset-password`."""

    model_config = ConfigDict(str_strip_whitespace=True)

    token: str
    new_password: str
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def _validate_new_password_strength(cls, value: str) -> str:
        return validate_strong_password(value)

    @model_validator(mode="after")
    def _validate_passwords_match(self) -> "ResetPasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("new_password and confirm_password do not match.")
        return self
