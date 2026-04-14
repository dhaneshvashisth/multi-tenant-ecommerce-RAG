import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.postgres import init_db_pool, get_pool
from kafka_workers.producer import publish_feedback


async def test():
    await init_db_pool()

    session_id = "test-session-feedback"
    tenant_id = "amazon"

    print("\n=== Sending feedback events via Kafka ===")

    for i in range(3):
        await publish_feedback(
            tenant_id=tenant_id,
            session_id=session_id,
            query=f"Test query {i+1}",
            response=f"Test response {i+1}",
            rating=-1,
            prompt_version=1,
        )
        print(f"Published thumbs down #{i+1}")

    print("\nWaiting 5 seconds for consumer to process...")
    await asyncio.sleep(5)

    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM feedback WHERE tenant_id = $1", tenant_id
        )
        print(f"\nFeedback rows in DB: {len(rows)}")
        for row in rows:
            print(f"  rating={row['rating']} query='{row['query']}'")

        # Check prompt avg score updated
        prompt_row = await conn.fetchrow(
            """
            SELECT version, avg_feedback_score
            FROM prompt_registry
            WHERE tenant_id = $1 AND is_active = TRUE
            """,
            tenant_id,
        )
        print(f"\nActive prompt: version={prompt_row['version']} avg_score={prompt_row['avg_feedback_score']}")


asyncio.run(test())