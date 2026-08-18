"""Request schema for user login."""

from pydantic import BaseModel, ConfigDict, EmailStr


class LoginRequest(BaseModel):
    """Payload for `POST /auth/login`."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str
