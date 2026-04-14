import logging
from langgraph.graph import StateGraph, END
from app.rag.state import RAGState
from app.rag.nodes.router import router_node
from app.rag.nodes.retriever import retriever_node
from app.rag.nodes.reranker import reranker_node
from app.rag.nodes.generator import generator_node
from app.rag.nodes.citation_builder import citation_builder_node

logger = logging.getLogger(__name__)


def should_continue(state: RAGState) -> str:
    """
    Conditional edge after router node.
    If query is invalid, skip retrieval+reranking+generation
    and go straight to citation_builder which will
    return the router's error message as the final response.

    Why conditional edges:
    - Core LangGraph feature — graph flow is dynamic
    - Invalid queries cost zero API calls
    - This pattern scales to complex routing logic
    """
    if state["is_valid_query"]:
        return "retriever"
    return "citation_builder"


def build_rag_graph() -> StateGraph:
    """Builds and compiles the 5-node RAG pipeline.
    Graph structure:
    router --> [conditional] --> retriever --> reranker --> generator --> citation_builder --> END
                    |
                    └── (invalid query) --> citation_builder --> END"""
    graph = StateGraph(RAGState)

    graph.add_node("router", router_node)
    graph.add_node("retriever", retriever_node)
    graph.add_node("reranker", reranker_node)
    graph.add_node("generator", generator_node)
    graph.add_node("citation_builder", citation_builder_node)

    graph.set_entry_point("router")

    graph.add_conditional_edges(
        "router",
        should_continue,
        {
            "retriever": "retriever",
            "citation_builder": "citation_builder",
        },
    )

    graph.add_edge("retriever", "reranker")
    graph.add_edge("reranker", "generator")
    graph.add_edge("generator", "citation_builder")
    graph.add_edge("citation_builder", END)

    compiled = graph.compile()
    logger.info("RAG graph compiled successfully")
    return compiled


# Singleton — compiled once, reused for every query
rag_graph = build_rag_graph()