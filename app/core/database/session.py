"""
Async SQLAlchemy engine/session factory and the FastAPI DB dependency.

This module owns the single engine and sessionmaker for the whole
application. Every feature's repository receives an `AsyncSession`
through the `get_db` dependency — nothing imports or constructs the
engine directly.
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,
    pool_timeout=30,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a transactional async DB session.

    Commits on clean exit, rolls back on exception, always closes the
    session afterward. Routes and services never call commit/rollback
    themselves — this is the single place that owns the transaction
    boundary for a request.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context-manager variant of `get_db` for use outside request scope
    (background tasks, scripts, seed data, scheduled jobs).

    Usage:
        async with get_db_context() as db:
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_connection() -> bool:
    """Run a trivial round-trip query to confirm the database is reachable.

    Used by the `/health` endpoint and at application startup so a broken
    DB connection fails fast and loudly instead of surfacing as a mystery
    500 on the first real request.
    """
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 - deliberately broad for a health probe
        logger.error("database_connection_failed", error=str(exc))
        return False


async def dispose_engine() -> None:
    """Cleanly dispose of the connection pool on application shutdown."""
    await engine.dispose()
    logger.info("database_engine_disposed")
