"""
Redis connection factory shared by caching and rate-limiting.
"""
import structlog
from redis.asyncio import ConnectionPool, Redis

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_pool = ConnectionPool.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
    max_connections=20,
)


def get_redis_client() -> Redis:
    """Return a Redis client bound to the shared connection pool."""
    return Redis(connection_pool=_pool)


async def close_redis_pool() -> None:
    """Cleanly disconnect the shared Redis connection pool on shutdown.

    Symmetric with `dispose_engine()` for the database — every long-lived
    connection pool the app owns gets an explicit, logged teardown instead
    of relying on process exit to clean it up.
    """
    await _pool.disconnect()
    logger.info("redis_pool_disconnected")
