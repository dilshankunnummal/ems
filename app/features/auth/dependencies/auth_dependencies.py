"""
Authentication and authorization dependency providers.

`current_user` / `current_active_user` decode the bearer access token
(via the shared `app.shared.security` JWT utilities) and load the
corresponding `User` row. `permission_required` is a dependency factory
that restricts a route to callers holding one of a given set of role
names.

Full attribute/resource-level permission logic (beyond simple role
membership) is out of scope for this foundation phase and lands with
the rest of the authorization flow later.
"""
import uuid
from collections.abc import Callable

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.features.auth.models.user import User
from app.features.auth.repository.user_repository import UserRepository
from app.shared.exceptions import ForbiddenException, UnauthorizedException
from app.shared.security import TokenType, decode_token

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login",
    auto_error=False,
)


async def current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the authenticated `User` from a bearer access token.

    Raises `UnauthorizedException` if no token was supplied, the token
    is invalid/expired, or it no longer maps to an existing user.
    """
    if not token:
        raise UnauthorizedException(
            "Not authenticated.", error_code="NOT_AUTHENTICATED"
        )

    payload = decode_token(token, expected_type=TokenType.ACCESS)

    try:
        user_id = uuid.UUID(payload.sub)
    except ValueError as exc:
        raise UnauthorizedException(
            "Could not validate credentials.", error_code="INVALID_CREDENTIALS"
        ) from exc

    user = await UserRepository(db).get_by_id(user_id)
    if user is None:
        raise UnauthorizedException(
            "Could not validate credentials.", error_code="INVALID_CREDENTIALS"
        )

    return user


async def current_active_user(user: User = Depends(current_user)) -> User:
    """Resolve the authenticated user and ensure the account is active."""
    if not user.is_active:
        raise ForbiddenException(
            "This user account has been deactivated.", error_code="USER_INACTIVE"
        )
    return user


def permission_required(*allowed_roles: str) -> Callable[..., User]:
    """Dependency factory restricting a route to users holding at least
    one of `allowed_roles`.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(permission_required("admin"))])
    """

    def _check_roles(user: User = Depends(current_active_user)) -> User:
        held_roles = {user_role.role.name for user_role in user.user_roles}
        if not held_roles.intersection(allowed_roles):
            raise ForbiddenException(
                "You do not have permission to perform this action.",
                error_code="INSUFFICIENT_PERMISSIONS",
            )
        return user

    return _check_roles