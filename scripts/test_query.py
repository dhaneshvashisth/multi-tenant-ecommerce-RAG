import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rag.graph import rag_graph
from app.db.postgres import init_db_pool
from app.db.qdrant import init_qdrant_client


async def test_query():
    await init_db_pool()
    await init_qdrant_client()

    initial_state = {
        "tenant_id": "amazon",
        "query": "What is the return window for electronics?",
        "session_id": "test-session-001",
        "conversation_history": [],
        "is_valid_query": False,
        "router_message": None,
        "retrieved_chunks": [],
        "reranked_chunks": [],
        "system_prompt": "",
        "raw_response": "",
        "final_response": "",
        "citations": [],
    }

    print("\n--- Running RAG Pipeline ---")
    print(f"Tenant: {initial_state['tenant_id']}")
    print(f"Query: {initial_state['query']}\n")

    result = await rag_graph.ainvoke(initial_state)

    print("--- Response ---")
    print(result["final_response"])
    print("\n--- Citations ---")
    for c in result["citations"]:
        print(f"  [{c['document_name']}] chunk {c['chunk_index']}: {c['text_snippet'][:80]}...")
        print(f"  Rerank score: {c['rerank_score']}")


asyncio.run(test_query())