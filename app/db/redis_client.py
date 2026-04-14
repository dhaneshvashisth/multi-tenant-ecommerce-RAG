import redis.asyncio as aioredis
import logging
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_redis: aioredis.Redis | None = None


async def init_redis_client() -> None:
    global _redis
    _redis = aioredis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        decode_responses=True,
    )
    # Verify connection
    await _redis.ping()
    logger.info("Redis client initialized")


async def close_redis_client() -> None:
    global _redis
    if _redis:
        await _redis.close()
        logger.info("Redis client closed")


def get_redis() -> aioredis.Redis:
    if _redis is None:
        raise RuntimeError("Redis client not initialized")
    return _redis