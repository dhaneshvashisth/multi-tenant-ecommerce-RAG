import asyncpg
import logging
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_pool: asyncpg.Pool | None = None


async def init_db_pool() -> None:
    """Creates the asyncpg connection pool also after that it runs schema migrations. Called once on FastAPI startup."""
    global _pool
    _pool = await asyncpg.create_pool(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
        min_size=2,
        max_size=10,
    )
    await _run_schema()
    logger.info("PostgreSQL connection pool has been initialized")


async def _run_schema() -> None:
    """Reads schema.sql and executes it against the database. Uses IF NOT EXISTS so it's safe to run on every startup"""
    import os
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r") as f:
        schema_sql = f.read()
    async with _pool.acquire() as conn:
        await conn.execute(schema_sql)
    logger.info("Database schema has been applied successfully")


async def close_db_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        logger.info("PostgreSQL connection pool has been closed")


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool has not been initialized")
    return _pool