import asyncio
import json
import logging
from aiokafka import AIOKafkaProducer
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

INGESTION_TOPIC = "document_ingestion"
FEEDBACK_TOPIC = "user_feedback"


async def publish_ingestion_job(tenant_id: str, document_path: str) -> None:
    """Publishes a document ingestion job to Kafka. The consumer picks this up and processes the PDF asynchronously.
    Why Kafka and not direct processing:
    - The API call returns immediately (non-blocking)
    - Heavy PDF processing happens in the background
    - If the consumer crashes, the message stays in Kafka and gets reprocessed
    - This is the production pattern for document ingestion at scale
    """
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    await producer.start()
    try:
        message = {
            "tenant_id": tenant_id,
            "document_path": document_path,
        }
        await producer.send_and_wait(INGESTION_TOPIC, message)
        logger.info(f"Published ingestion job: tenant={tenant_id}, doc={document_path}")
    finally:
        await producer.stop()


async def publish_feedback(tenant_id: str, session_id: str, query: str, response: str, rating: int, prompt_version: int = 1) -> None:
    """Publishes user feedback to Kafka.The feedback consumer writes this to PostgreSQL. Rating: 1 = thumbs up, -1 = thumbs down """
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    await producer.start()
    try:
        message = {
            "tenant_id": tenant_id,
            "session_id": session_id,
            "query": query,
            "response": response,
            "rating": rating,
            "prompt_version": prompt_version,
        }
        await producer.send_and_wait(FEEDBACK_TOPIC, message)
        logger.info(f"Published feedback: tenant={tenant_id}, rating={rating}")
    finally:
        await producer.stop()