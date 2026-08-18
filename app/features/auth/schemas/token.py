"""Token response/request schemas shared by login, refresh, and logout."""

from pydantic import BaseModel, ConfigDict


class TokenResponse(BaseModel):
    """Response body returned on successful login or token refresh."""

    model_config = ConfigDict(from_attributes=True)

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    """Payload for `POST /auth/refresh` and `POST /auth/logout`."""

    model_config = ConfigDict(str_strip_whitespace=True)

    refresh_token: str
