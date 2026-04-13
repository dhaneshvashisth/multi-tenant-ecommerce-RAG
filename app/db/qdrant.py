from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (Distance, VectorParams, PointStruct)
import logging
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_client: AsyncQdrantClient | None = None

VECTOR_SIZE = 1536 
DISTANCE = Distance.COSINE


def get_collection_name(tenant_id: str) -> str:
    """Maps tenant ID to Qdrant collection name: amazon -> amazon_policies, flipkart -> flipkart_policies"""
    return (f"{tenant_id}_policies")


async def init_qdrant_client() -> None:
    global _client
    _client = AsyncQdrantClient(host=settings.qdrant_host,  port=settings.qdrant_port )
    logger.info("Qdrant client is initialized")


async def close_qdrant_client() -> None:
    global _client
    if _client:
        await _client.close()
        logger.info("Qdrant client has been closed")


def get_qdrant_client() -> AsyncQdrantClient:
    if _client is None:
        raise RuntimeError("Qdrant client not initialized")
    return _client


async def ensure_collection(tenant_id: str) -> None:
    """Creates a Qdrant collection for the tenant if it doesn't exist. Safe to call multiple times — checks before creating."""
    client = get_qdrant_client()
    collection_name = get_collection_name(tenant_id)

    existing = await client.get_collections()
    existing_names = [c.name for c in existing.collections]

    if collection_name not in existing_names:
        await client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=DISTANCE,
            ),
        )
        logger.info(f"Created Qdrant collection: {collection_name}")
    else:
        logger.info(f"Collection already exists: {collection_name}")


async def upsert_chunks( tenant_id: str,  chunks: list[dict],) -> None:
    """ Upserts embedded chunks into the tenant's Qdrant collection.
    Each chunk dict must have:
        - id: unique string ID
        - embedding: list[float] (1536 dims)
        - text: original chunk text
        - metadata: dict with source doc info """
    
    client = get_qdrant_client()
    collection_name = get_collection_name(tenant_id)

    points = [
        PointStruct(
            id = chunk["id"],
            vector = chunk["embedding"],
            payload = {
                "text": chunk["text"],
                "tenant_id": tenant_id,
                **chunk["metadata"],
            },
        )
        for chunk in chunks
    ]

    await client.upsert(
        collection_name=collection_name,
        points=points,
    )
    logger.info(f"Upserted {len(points)} chunks into {collection_name}")