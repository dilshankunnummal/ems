"""Request/response schemas for role-management endpoints."""
from pydantic import BaseModel, ConfigDict, Field


class RoleAssignRequest(BaseModel):
    """Payload for `POST /users/{user_id}/roles`."""

    model_config = ConfigDict(str_strip_whitespace=True)

    role_name: str = Field(..., min_length=1, max_length=50)


class RoleResponse(BaseModel):
    """A single role name, as held by a user."""

    model_config = ConfigDict(from_attributes=True)

    name: str


class UserRolesResponse(BaseModel):
    """The full set of roles currently held by a user."""

    model_config = ConfigDict(from_attributes=True)

    user_id: str
    roles: list[str]
