import logging
from app.rag.state import RAGState

logger = logging.getLogger(__name__)


async def citation_builder_node(state: RAGState) -> dict:
    """
    Node 5: Attaches source citations to the response.

    Why citations matter:
    - Customer support answers must be verifiable
    - Reduces hallucination trust issues
    - Lets the frontend show "Source: return_policy.txt"
    - Critical for enterprise RAG — auditors want to know
      where every answer came from

    Format:
    {
        "chunk_index": 0,
        "document_name": "return_policy.txt",
        "text_snippet": "first 150 chars of the chunk..."
    }
    """
    raw_response = state["raw_response"]
    reranked_chunks = state.get("reranked_chunks", [])

    citations = [
        {
            "chunk_index": chunk.get("chunk_index", i),
            "document_name": chunk.get("document_name", "unknown"),
            "text_snippet": chunk["text"][:150] + "..." if len(chunk["text"]) > 150 else chunk["text"],
            "rerank_score": round(chunk.get("rerank_score", 0.0), 4),
        }
        for i, chunk in enumerate(reranked_chunks)
    ]

    # Final response = raw response + citation note
    if citations:
        source_names = list({c["document_name"] for c in citations})
        final_response = raw_response
    else:
        final_response = raw_response

    logger.info(f"Citation builder: attached {len(citations)} citations")
    return {
        "final_response": final_response,
        "citations": citations,
    }