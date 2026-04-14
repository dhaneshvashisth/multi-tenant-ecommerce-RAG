import json
import logging
from app.db.redis_client import get_redis

logger = logging.getLogger(__name__)

MEMORY_PREFIX = "conversation"
MEMORY_TTL_SECONDS = 1800  
MAX_HISTORY_TURNS = 10   


async def get_conversation_history(
    tenant_id: str,
    session_id: str,
) -> list[dict]:
    """
    Retrieves conversation history for a session.
    Returns list of {role, content} dicts for OpenAI message format.

    Why Redis for memory:
    - Sub-millisecond reads
    - TTL auto-clears inactive sessions
    - Scales horizontally — any API instance reads the same memory
    - Stateless API + stateful Redis = production pattern
    """
    redis = get_redis()
    key = f"{MEMORY_PREFIX}:{tenant_id}:{session_id}"
    data = await redis.get(key)
    if not data:
        return []
    return json.loads(data)


async def append_to_conversation(
    tenant_id: str,
    session_id: str,
    query: str,
    response: str,
) -> None:
    """
    Appends a query-response pair to the session history.
    Trims to MAX_HISTORY_TURNS to prevent unbounded growth.
    Resets TTL on every interaction.
    """
    redis = get_redis()
    key = f"{MEMORY_PREFIX}:{tenant_id}:{session_id}"

    history = await get_conversation_history(tenant_id, session_id)

    history.append({"role": "user", "content": query})
    history.append({"role": "assistant", "content": response})

    if len(history) > MAX_HISTORY_TURNS * 2:
        history = history[-(MAX_HISTORY_TURNS * 2):]

    await redis.setex(key, MEMORY_TTL_SECONDS, json.dumps(history))
    logger.info(
        f"Memory updated: tenant={tenant_id} "
        f"session={session_id} turns={len(history)//2}"
    )


async def clear_conversation(tenant_id: str, session_id: str) -> None:
    redis = get_redis()
    key = f"{MEMORY_PREFIX}:{tenant_id}:{session_id}"
    await redis.delete(key)
    logger.info(f"Memory cleared: tenant={tenant_id} session={session_id}")