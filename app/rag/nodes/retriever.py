import logging
from openai import AsyncOpenAI
from app.rag.state import RAGState
from app.db.qdrant import get_qdrant_client, get_collection_name
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

EMBEDDING_MODEL = "text-embedding-3-small"
TOP_K_RETRIEVAL = 10  # retrieve more, reranker will filter down to top 3-5


async def retriever_node(state: RAGState) -> dict:
    """
    Node 2: Semantic retrieval from Qdrant.

    Steps:
    1. Embed the query using OpenAI text-embedding-3-small
    2. Search the tenant's Qdrant collection
    3. Return top-K chunks for reranking

    Why TOP_K=10 before reranking:
    - Vector similarity alone is imprecise
    - We retrieve more candidates and let FlashRank
      pick the truly relevant ones
    - This is the standard production RAG pattern
    """
    if not state["is_valid_query"]:
        return {"retrieved_chunks": []}

    tenant_id = state["tenant_id"]
    query = state["query"]

    # Step 1: Embed query
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=query,
    )
    query_embedding = response.data[0].embedding

    # Step 2: Search Qdrant
    qdrant_client = get_qdrant_client()
    collection_name = get_collection_name(tenant_id)

    search_results = await qdrant_client.search(
        collection_name=collection_name,
        query_vector=query_embedding,
        limit=TOP_K_RETRIEVAL,
        with_payload=True,
    )

    # Step 3: Format results
    chunks = [
        {
            "text": hit.payload.get("text", ""),
            "document_name": hit.payload.get("document_name", ""),
            "chunk_index": hit.payload.get("chunk_index", 0),
            "score": hit.score,
        }
        for hit in search_results
    ]

    logger.info(f"Retriever: found {len(chunks)} chunks for tenant={tenant_id}")
    return {"retrieved_chunks": chunks}