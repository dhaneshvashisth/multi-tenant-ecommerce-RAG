from typing import TypedDict, Optional


class RAGState(TypedDict):
    """Shared state passed between all LangGraph nodes.
    Flow:
    router -> retriever -> reranker -> generator -> citation_builder
    Each node reads what it needs and adds its output.
    Nothing is mutated — each node returns a partial dict
    that LangGraph merges into the state."""
    tenant_id: str
    query: str
    session_id: str
    conversation_history: list[dict]

    is_valid_query: bool
    router_message: Optional[str]
    retrieved_chunks: list[dict]  

    reranked_chunks: list[dict] 

    system_prompt: str
    raw_response: str

    final_response: str
    citations: list[dict] 