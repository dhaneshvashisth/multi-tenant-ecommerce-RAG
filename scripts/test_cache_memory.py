import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.postgres import init_db_pool
from app.db.qdrant import init_qdrant_client
from app.db.redis_client import init_redis_client
from app.db.prompt_registry import seed_default_prompts
from app.rag.pipeline import query_rag


async def test():
    await init_db_pool()
    await init_qdrant_client()
    await init_redis_client()
    await seed_default_prompts()

    session_id = "test-session-phase4"
    tenant_id = "amazon"

    print("\n=== Turn 1: First query (expect cache MISS) ===")
    result1 = await query_rag(
        tenant_id=tenant_id,
        query="What is the return window for electronics?",
        session_id=session_id,
    )
    print(f"Cache hit: {result1['cache_hit']}")
    print(f"Response: {result1['final_response'][:150]}")

    print("\n=== Turn 2: Similar query (expect cache HIT) ===")
    result2 = await query_rag(
        tenant_id=tenant_id,
        query="How many days do I have to return electronics?",
        session_id=session_id,
    )
    print(f"Cache hit: {result2['cache_hit']}")
    if result2['cache_hit']:
        print(f"Similarity score: {result2['similarity_score']:.4f}")
    print(f"Response: {result2['final_response'][:150]}")

    print("\n=== Turn 3: Follow-up question (tests memory) ===")
    result3 = await query_rag(
        tenant_id=tenant_id,
        query="What about the restocking fee mentioned earlier?",
        session_id=session_id,
    )
    print(f"Cache hit: {result3['cache_hit']}")
    print(f"Response: {result3['final_response'][:150]}")


asyncio.run(test())