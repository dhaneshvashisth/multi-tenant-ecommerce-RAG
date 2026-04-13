import asyncio
import json
import logging
import uuid
import os
from aiokafka import AIOKafkaConsumer
from openai import AsyncOpenAI
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings
from app.db.postgres import init_db_pool, get_pool
from app.db.qdrant import init_qdrant_client, ensure_collection, upsert_chunks

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()

INGESTION_TOPIC = "document_ingestion"
CHUNK_SIZE = 512
CHUNK_OVERLAP = 64
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_BATCH_SIZE = 50


async def extract_text_from_pdf(document_path: str) -> str:
    """Reads a PDF file and extracts all text"""
    reader = PdfReader(document_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text.strip()


async def chunk_text(text: str) -> list[str]:
    """Splits text into overlapping chunks using LangChain's RecursiveCharacterTextSplitter.
    Why recursive splitter:
    - Tries to split on paragraphs first, then sentences, then words
    - Preserves semantic boundaries better than naive character splitting
    - Overlap ensures context isn't lost at chunk boundaries
    CHUNK_SIZE=512: Balances retrieval precision vs context richness
    CHUNK_OVERLAP=64: ~12% overlap — enough for boundary continuity
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)


async def generate_embeddings(chunks: list[str], openai_client: AsyncOpenAI) -> list[list[float]]:
    """ Generates embeddings for all chunks in batches.

    Why batching:
    - OpenAI embedding API has a token limit per request
    - Batching reduces number of API calls (cost + latency)
    - EMBEDDING_BATCH_SIZE=50 is safe for 512-token chunks
    """
    all_embeddings = []
    for i in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
        batch = chunks[i: i + EMBEDDING_BATCH_SIZE]
        response = await openai_client.embeddings.create(model=EMBEDDING_MODEL, input=batch )

        batch_embeddings = [item.embedding for item in response.data]

        all_embeddings.extend(batch_embeddings)
        logger.info(f"Embedded batch {i // EMBEDDING_BATCH_SIZE + 1}, {len(batch)} chunks")

    return all_embeddings


async def write_audit_log(tenant_id: str, document_name: str, chunk_count: int, status: str = "success", error_message: str = None) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO ingestion_audit
                (tenant_id, document_name, chunk_count, status, error_message)
            VALUES ($1, $2, $3, $4, $5)
            """,
            tenant_id,
            document_name,
            chunk_count,
            status,
            error_message,
        )


async def process_ingestion_message( message: dict, openai_client: AsyncOpenAI) -> None:
    """
    Core ingestion logic. Called for each Kafka message.

    Flow:
    1. Extract text from PDF
    2. Chunk text
    3. Generate embeddings in batches
    4. Ensure Qdrant collection exists for tenant
    5. Upsert chunks with embeddings
    6. Write audit log
    """
    tenant_id = message["tenant_id"]
    document_path = message["document_path"]
    document_name = os.path.basename(document_path)

    logger.info(f"Processing: tenant={tenant_id}, doc={document_name}")

    try:
        text = await extract_text_from_pdf(document_path)
        if not text:
            raise ValueError(f"No text extracted from {document_name}")

        chunks = await chunk_text(text)
        logger.info(f"Created {len(chunks)} chunks from {document_name}")

        embeddings = await generate_embeddings(chunks, openai_client)

        await ensure_collection(tenant_id)

        chunk_dicts = [
            {
                "id": abs(hash(f"{tenant_id}_{document_name}_{i}")) % (2**63),
                "embedding": embeddings[i],
                "text": chunks[i],
                "metadata": {
                    "document_name": document_name,
                    "chunk_index": i,
                    "tenant_id": tenant_id,
                },
            }
            for i in range(len(chunks))
        ]
        await upsert_chunks(tenant_id, chunk_dicts)

        await write_audit_log(tenant_id, document_name, len(chunks))
        logger.info(f"Successfully ingested {document_name} for tenant {tenant_id}")

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        await write_audit_log(
            tenant_id, document_name, 0,
            status="failed",
            error_message=str(e),
        )


async def run_consumer() -> None:
    """
    Main consumer loop. Runs forever, processing ingestion jobs.
    """
    await init_db_pool()
    await init_qdrant_client()

    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

    consumer = AIOKafkaConsumer(
        INGESTION_TOPIC,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id="ingestion_consumer_group",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
    )

    await consumer.start()
    logger.info(f"Ingestion consumer started, listening to topic: {INGESTION_TOPIC}")

    try:
        async for msg in consumer:
            await process_ingestion_message(msg.value, openai_client)
    finally:
        await consumer.stop()


if __name__ == "__main__":
    asyncio.run(run_consumer())