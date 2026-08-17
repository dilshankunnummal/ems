"""
Data-access layer for the RefreshToken model.

Contains only database operations — rotation policy (revoke-on-refresh,
reuse detection, etc.) belongs to the service layer.
"""
import uuid
from datetime import datetime

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.models.user import RefreshToken

logger = structlog.get_logger(__name__)


class RefreshTokenRepository:
    """Async repository providing basic persistence operations for `RefreshToken`."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        token: str,
        expires_at: datetime,
    ) -> RefreshToken:
        """Persist a newly issued refresh token."""
        refresh_token = RefreshToken(
            user_id=user_id,
            token=token,
            expires_at=expires_at,
            revoked=False,
        )
        self.db.add(refresh_token)
        await self.db.flush()
        await self.db.refresh(refresh_token)
        return refresh_token

    async def get_by_token(self, token: str) -> RefreshToken | None:
        """Fetch a refresh token row by its raw token string."""
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token == token)
        )
        return result.scalar_one_or_none()

    async def revoke(self, token: str) -> bool:
        """Mark a refresh token as revoked.

        Returns True if a matching, not-yet-revoked row was updated,
        False if no such token exists (already revoked or unknown).
        """
        result = await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.token == token, RefreshToken.revoked.is_(False))
            .values(revoked=True)
        )
        revoked = result.rowcount > 0
        if not revoked:
            logger.info("refresh_token_revoke_noop", token_prefix=token[:12])
        return revoked

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        """Revoke every active refresh token for a user.

        Called on password change/reset so every other logged-in session
        is forced to re-authenticate — that's the entire point of
        invalidating a password that may have been compromised.
        """
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
            .values(revoked=True)
        )
        await self.db.execute(stmt)
        await self.db.flush()