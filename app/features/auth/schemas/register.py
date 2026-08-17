"""Request schema for user registration."""
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator

from app.shared.validators.common import validate_strong_password


class RegisterRequest(BaseModel):
    """Payload for `POST /auth/register`."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str
    confirm_password: str

    @field_validator("password")
    @classmethod
    def _validate_password_strength(cls, value: str) -> str:
        return validate_strong_password(value)

    @model_validator(mode="after")
    def _validate_passwords_match(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("password and confirm_password do not match.")
        return self