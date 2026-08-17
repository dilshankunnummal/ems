
"""
Data-access layer for the User model.

Contains only database operations — no password hashing, token issuing,
or other business rules. Those belong to the service layer, wired up in
a later phase.
"""
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.models.user import User
from app.shared.exceptions import ConflictException

logger = structlog.get_logger(__name__)


class UserRepository:
    """Async repository providing basic persistence operations for `User`."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Fetch a user by primary key, or None if it doesn't exist."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Fetch a user by email (case-insensitive), or None if it doesn't exist."""
        result = await self.db.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        email: str,
        hashed_password: str,
        is_active: bool = True,
        is_verified: bool = False,
    ) -> User:
        """Persist a new user row.

        Expects an already-hashed password — hashing is the caller's
        (service layer's) responsibility, not the repository's.
        """
        user = User(
            email=email.lower(),
            hashed_password=hashed_password,
            is_active=is_active,
            is_verified=is_verified,
        )
        self.db.add(user)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            logger.warning("user_create_conflict", email=email)
            raise ConflictException(
                "A user with this email address already exists.",
                error_code="USER_ALREADY_EXISTS",
            ) from exc
        await self.db.refresh(user)
        return user