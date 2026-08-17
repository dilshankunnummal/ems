"""
Role-management service — grants and revokes roles on existing users.

Kept separate from `AuthService`: that service owns the self-service
identity lifecycle (register/login/password/verification); this one
owns admin-driven changes to *other* users' permissions. Different
caller, different audit/authorization shape, so it's a different class.
"""
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.exceptions.auth_exceptions import (
    RoleAlreadyAssignedException,
    RoleNotAssignedException,
    RoleNotFoundException,
)
from app.features.auth.models.user import User
from app.features.auth.repository.role_repository import RoleRepository
from app.features.auth.repository.user_repository import UserRepository
from app.shared.exceptions import NotFoundException

logger = structlog.get_logger(__name__)


class RoleService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.roles = RoleRepository(db)

    async def _get_user_or_404(self, email: str) -> User:
        user = await self.users.get_by_email(email)
        if user is None:
            raise NotFoundException("User not found.", error_code="USER_NOT_FOUND")
        return user

    async def list_user_roles(self, email: str) -> User:
        """Return the user (with `user_roles` loaded) so the caller can
        read their current role names.
        """
        return await self._get_user_or_404(email)

    async def assign_role(
        self, email: str, role_name: str, *, granted_by: UUID
    ) -> User:
        """Grant `role_name` to the user with the given email.

        Raises `RoleNotFoundException` if the role doesn't exist yet —
        deliberately NOT auto-creating it here (unlike the self-service
        "employee" default in `AuthService.register`), since a typo'd
        role name from an admin should surface as an error, not silently
        create a new, possibly-misspelled permission group.
        """
        user = await self._get_user_or_404(email)

        role = await self.roles.get_by_name(role_name)
        if role is None:
            raise RoleNotFoundException(role_name)

        existing = await self.roles.get_user_role_link(user.id, role.id)
        if existing is not None:
            raise RoleAlreadyAssignedException(role_name)

        await self.roles.assign_role(user.id, role.id)
        await self.db.commit()
        await self.db.refresh(user)

        logger.info(
            "role_assigned",
            user_id=str(user.id),
            role=role_name,
            granted_by=str(granted_by),
        )
        return user

    async def revoke_role(
        self, email: str, role_name: str, *, revoked_by: UUID
    ) -> User:
        """Revoke `role_name` from the user with the given email."""
        user = await self._get_user_or_404(email)

        role = await self.roles.get_by_name(role_name)
        if role is None:
            raise RoleNotFoundException(role_name)

        link = await self.roles.get_user_role_link(user.id, role.id)
        if link is None:
            raise RoleNotAssignedException(role_name)

        await self.roles.revoke_role(link)
        await self.db.commit()
        await self.db.refresh(user)

        logger.info(
            "role_revoked",
            user_id=str(user.id),
            role=role_name,
            revoked_by=str(revoked_by),
        )
        return user