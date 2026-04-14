import logging
from flashrank import Ranker, RerankRequest
from app.rag.state import RAGState

logger = logging.getLogger(__name__)

TOP_K_RERANK = 3  # final number of chunks passed to generator

# Initialize FlashRank ranker once (model downloads on first use)
_ranker: Ranker | None = None


def get_ranker() -> Ranker:
    global _ranker
    if _ranker is None:
        _ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir="/tmp/flashrank")
        logger.info("FlashRank ranker initialized")
    return _ranker


async def reranker_node(state: RAGState) -> dict:
    """
    Node 3: Cross-encoder reranking with FlashRank.

    Why reranking matters:
    - Vector similarity finds semantically similar text
    - But similar != relevant to the specific question
    - Cross-encoders jointly encode query + document
      giving far more precise relevance scores
    - Example: "What is the return window?" retrieves
      chunks about windows (OS) at vector level,
      reranker correctly scores those as irrelevant

    FlashRank runs locally — no API cost, ~50ms latency.
    """
    if not state["is_valid_query"]:
        return {"reranked_chunks": []}

    chunks = state["retrieved_chunks"]
    if not chunks:
        return {"reranked_chunks": []}

    query = state["query"]
    ranker = get_ranker()

    # Format for FlashRank
    passages = [
        {"id": i, "text": chunk["text"]}
        for i, chunk in enumerate(chunks)
    ]

    rerank_request = RerankRequest(query=query, passages=passages)
    results = ranker.rerank(rerank_request)

    # Take top-K and map back to original chunk data
    top_results = results[:TOP_K_RERANK]
    reranked_chunks = [
        {
            **chunks[r["id"]],
            "rerank_score": r["score"],
        }
        for r in top_results
    ]

    logger.info(f"Reranker: kept {len(reranked_chunks)} chunks from {len(chunks)}")
    return {"reranked_chunks": reranked_chunks}