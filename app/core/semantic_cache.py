import json
import hashlib
import logging
import numpy as np
from openai import AsyncOpenAI
from app.db.redis_client import get_redis
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

CACHE_SIMILARITY_THRESHOLD = 0.92
CACHE_TTL_SECONDS = 3600  # 1 hour
EMBEDDING_MODEL = "text-embedding-3-small"
CACHE_PREFIX = "semantic_cache"


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """
    Computes cosine similarity between two embedding vectors.
    Returns a value between -1 and 1. Higher = more similar.
    We use 0.92 as threshold — tight enough to avoid false hits.
    """
    a = np.array(vec1)
    b = np.array(vec2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


async def get_query_embedding(query: str) -> list[float]:
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=query,
    )
    return response.data[0].embedding


async def get_cached_response(
    tenant_id: str,
    query: str,
    query_embedding: list[float],
) -> dict | None:
    """
    Checks Redis for a semantically similar cached query.

    How it works:
    1. Scan all cache keys for this tenant
    2. Load each cached embedding
    3. Compute cosine similarity with current query embedding
    4. If similarity > threshold, return cached response

    Why not exact key match:
    - "What is return policy?" != "How do I return something?"
    - But they mean the same thing — semantic cache handles both
    """
    redis = get_redis()
    pattern = f"{CACHE_PREFIX}:{tenant_id}:*"
    keys = await redis.keys(pattern)

    for key in keys:
        cached_data = await redis.get(key)
        if not cached_data:
            continue

        cached = json.loads(cached_data)
        cached_embedding = cached.get("query_embedding")
        if not cached_embedding:
            continue

        similarity = cosine_similarity(query_embedding, cached_embedding)
        if similarity >= CACHE_SIMILARITY_THRESHOLD:
            logger.info(
                f"Cache HIT for tenant={tenant_id} "
                f"similarity={similarity:.4f} query='{query[:50]}'"
            )
            return {
                "final_response": cached["final_response"],
                "citations": cached["citations"],
                "cache_hit": True,
                "similarity": similarity,
            }

    return None


async def set_cached_response(
    tenant_id: str,
    query: str,
    query_embedding: list[float],
    final_response: str,
    citations: list[dict],
) -> None:
    """
    Stores query embedding + response in Redis with TTL.
    Key is a hash of tenant_id + query for uniqueness.
    """
    redis = get_redis()
    key_hash = hashlib.md5(f"{tenant_id}:{query}".encode()).hexdigest()
    key = f"{CACHE_PREFIX}:{tenant_id}:{key_hash}"

    payload = {
        "query": query,
        "query_embedding": query_embedding,
        "final_response": final_response,
        "citations": citations,
    }

    await redis.setex(key, CACHE_TTL_SECONDS, json.dumps(payload))
    logger.info(f"Cache SET for tenant={tenant_id} query='{query[:50]}'")