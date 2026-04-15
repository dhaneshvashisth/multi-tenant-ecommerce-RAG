from fastapi import APIRouter
from app.schemas.responses import HealthResponse, ServiceStatus
from app.core.config import get_settings
from app.db.postgres import get_pool
from app.db.qdrant import get_qdrant_client
from app.db.redis_client import get_redis
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


async def check_postgres() -> str:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return "healthy"
    except Exception as e:
        logger.error(f"Postgres health check failed: {e}")
        return "unhealthy"


async def check_qdrant() -> str:
    try:
        client = get_qdrant_client()
        await client.get_collections()
        return "healthy"
    except Exception as e:
        logger.error(f"Qdrant health check failed: {e}")
        return "unhealthy"


async def check_redis() -> str:
    try:
        redis = get_redis()
        await redis.ping()
        return "healthy"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return "unhealthy"


@router.get( "/health",   response_model=HealthResponse,summary="Check health of all services", tags=["Health"])
async def health_check():
    postgres_status = await check_postgres()
    qdrant_status = await check_qdrant()
    redis_status = await check_redis()

    all_healthy = all(
        s == "healthy"
        for s in [postgres_status, qdrant_status, redis_status]
    )

    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        app_env=settings.app_env,
        version="1.0.0",
        services=ServiceStatus(
            status="healthy" if all_healthy else "degraded",
            postgres=postgres_status,
            qdrant=qdrant_status,
            redis=redis_status,
            kafka="healthy",
        ),
    )