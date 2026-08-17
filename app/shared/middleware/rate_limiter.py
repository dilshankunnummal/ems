"""
Redis-backed rate limiting, built on `fastapi-limiter`.

`init_rate_limiter()` is called once from the app lifespan on startup.
Individual routes then opt in with a dependency:

    from fastapi_limiter.depends import RateLimiter
    @router.post("/login", dependencies=[Depends(RateLimiter(times=5, seconds=60))])

A default limiter (`default_rate_limiter`) is provided for routes that
just want the app-wide configured limit without picking custom numbers.
"""
import structlog
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

from app.core.common.redis_client import get_redis_client
from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


async def init_rate_limiter() -> None:
    """Bind fastapi-limiter to the shared Redis client. Call once at startup."""
    redis_client = get_redis_client()
    await FastAPILimiter.init(redis_client)
    logger.info(
        "rate_limiter_initialized",
        default_times=settings.RATE_LIMIT_TIMES,
        default_seconds=settings.RATE_LIMIT_SECONDS,
    )


async def close_rate_limiter() -> None:
    """Release the fastapi-limiter Redis binding on shutdown."""
    await FastAPILimiter.close()


def default_rate_limiter() -> RateLimiter:
    """A RateLimiter instance using the app-wide configured defaults.

    Usage: dependencies=[Depends(default_rate_limiter())]
    """
    return RateLimiter(times=settings.RATE_LIMIT_TIMES, seconds=settings.RATE_LIMIT_SECONDS)
