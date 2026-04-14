import logging
from app.rag.graph import rag_graph
from app.core.semantic_cache import (
    get_query_embedding,
    get_cached_response,
    set_cached_response,
)
from app.core.conversation_memory import (
    get_conversation_history,
    append_to_conversation,
)

logger = logging.getLogger(__name__)


async def query_rag(
    tenant_id: str,
    query: str,
    session_id: str,
) -> dict:
    """
    Main entry point for all RAG queries.

    Full flow:
    1. Embed query
    2. Check semantic cache → return instantly if hit
    3. Load conversation history from Redis
    4. Run LangGraph pipeline
    5. Store response in semantic cache
    6. Append turn to conversation memory
    7. Return response + citations + metadata

    This function is called by the FastAPI /query endpoint (Phase 6).
    """

    logger.info(f"Query received: tenant={tenant_id} session={session_id}")
    query_embedding = await get_query_embedding(query)

    cached = await get_cached_response(tenant_id, query, query_embedding)
    if cached:
        return {
            "tenant_id": tenant_id,
            "query": query,
            "session_id": session_id,
            "final_response": cached["final_response"],
            "citations": cached["citations"],
            "cache_hit": True,
            "similarity_score": cached["similarity"],
        }

    conversation_history = await get_conversation_history(tenant_id, session_id)
    logger.info(f"Loaded {len(conversation_history)//2} prior turns for session={session_id}")

    initial_state = {
        "tenant_id": tenant_id,
        "query": query,
        "session_id": session_id,
        "conversation_history": conversation_history,
        "is_valid_query": False,
        "router_message": None,
        "retrieved_chunks": [],
        "reranked_chunks": [],
        "system_prompt": "",
        "raw_response": "",
        "final_response": "",
        "citations": [],
    }

    result = await rag_graph.ainvoke(initial_state)

    final_response = result["final_response"]
    citations = result["citations"]

    if result["is_valid_query"] and final_response:
        await set_cached_response(
            tenant_id, query, query_embedding, final_response, citations
        )

    await append_to_conversation(tenant_id, session_id, query, final_response)

    return {
        "tenant_id": tenant_id,
        "query": query,
        "session_id": session_id,
        "final_response": final_response,
        "citations": citations,
        "cache_hit": False,
        "similarity_score": None,
    }