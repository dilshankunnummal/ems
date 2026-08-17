"""
Data-access layer for the Role model.

Contains only database operations — role-assignment rules and default
role seeding belong to the service layer.
"""
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.models.user import Role
from app.shared.exceptions import ConflictException

logger = structlog.get_logger(__name__)


class RoleRepository:
    """Async repository providing basic persistence operations for `Role`."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, role_id: uuid.UUID) -> Role | None:
        """Fetch a role by primary key, or None if it doesn't exist."""
        result = await self.db.execute(select(Role).where(Role.id == role_id))
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Role | None:
        """Fetch a role by its unique name, or None if it doesn't exist."""
        result = await self.db.execute(select(Role).where(Role.name == name))
        return result.scalar_one_or_none()

    async def create(self, *, name: str, description: str | None = None) -> Role:
        """Persist a new role row."""
        role = Role(name=name, description=description)
        self.db.add(role)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            logger.warning("role_create_conflict", name=name)
            raise ConflictException(
                "A role with this name already exists.",
                error_code="ROLE_ALREADY_EXISTS",
            ) from exc
        await self.db.refresh(role)
        return role