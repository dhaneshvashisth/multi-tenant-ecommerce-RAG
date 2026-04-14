import asyncio
import json
import logging
from aiokafka import AIOKafkaConsumer
from app.core.config import get_settings
from app.db.postgres import init_db_pool, get_pool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()

FEEDBACK_TOPIC = "user_feedback"


async def write_feedback_to_db(message: dict) -> None:
    """
    Writes a feedback event to PostgreSQL.

    Steps:
    1. Insert into feedback table
    2. Recompute avg_feedback_score for the tenant's active prompt
    3. Update prompt_registry with new average

    Why update avg on every feedback:
    - Phase 5 optimization job reads this score
    - Always up to date — no batch aggregation needed
    - Simple running average is sufficient for this use case
    """
    tenant_id = message["tenant_id"]
    session_id = message["session_id"]
    query = message["query"]
    response = message["response"]
    rating = message["rating"]
    prompt_version = message.get("prompt_version", 1)

    pool = get_pool()
    async with pool.acquire() as conn:
        # Step 1: Insert feedback
        await conn.execute(
            """
            INSERT INTO feedback
                (tenant_id, session_id, query, response, rating, prompt_version)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            tenant_id,
            session_id,
            query,
            response,
            rating,
            prompt_version,
        )
        logger.info(
            f"Feedback written: tenant={tenant_id} "
            f"rating={rating} session={session_id}"
        )

        # Step 2: Recompute average score for this prompt version
        avg_row = await conn.fetchrow(
            """
            SELECT AVG(rating::float) as avg_score
            FROM feedback
            WHERE tenant_id = $1 AND prompt_version = $2
            """,
            tenant_id,
            prompt_version,
        )
        avg_score = avg_row["avg_score"] if avg_row["avg_score"] else 0.0

        # Step 3: Update prompt registry
        await conn.execute(
            """
            UPDATE prompt_registry
            SET avg_feedback_score = $1
            WHERE tenant_id = $2
              AND version = $3
              AND is_active = TRUE
            """,
            avg_score,
            tenant_id,
            prompt_version,
        )
        logger.info(
            f"Prompt avg score updated: tenant={tenant_id} "
            f"version={prompt_version} avg={avg_score:.3f}"
        )


async def run_feedback_consumer() -> None:
    """
    Main feedback consumer loop.
    Runs forever, processing feedback events.
    """
    await init_db_pool()

    consumer = AIOKafkaConsumer(
        FEEDBACK_TOPIC,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id="feedback_consumer_group",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
    )

    await consumer.start()
    logger.info(f"Feedback consumer started, listening to: {FEEDBACK_TOPIC}")

    try:
        async for msg in consumer:
            await write_feedback_to_db(msg.value)
    finally:
        await consumer.stop()


if __name__ == "__main__":
    asyncio.run(run_feedback_consumer())