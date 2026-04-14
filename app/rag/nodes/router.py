import logging
from app.rag.state import RAGState

logger = logging.getLogger(__name__)

VALID_TENANTS = {"amazon", "flipkart", "myntra"}

IRRELEVANT_KEYWORDS = [
    "weather", "news", "sports", "movie", "recipe",
    "stock price", "cricket", "politics"
]


async def router_node(state: RAGState) -> dict:
    """
    Node 1: Validates the incoming query.

    Checks:
    1. Tenant ID is valid
    2. Query is not empty
    3. Query is not obviously off-topic

    Why this node exists:
    - Saves OpenAI API cost on invalid/irrelevant queries
    - Gives clear error messages instead of hallucinated responses
    - In production, this would call an LLM classifier for better accuracy
    """
    tenant_id = state["tenant_id"]
    query = state["query"].strip()

    if tenant_id not in VALID_TENANTS:
        logger.warning(f"Invalid tenant: {tenant_id}")
        return {
            "is_valid_query": False,
            "router_message": f"Unknown tenant: {tenant_id}. Valid tenants are: {', '.join(VALID_TENANTS)}",
        }

    if not query or len(query) < 5:
        return {
            "is_valid_query": False,
            "router_message": "Query is too short or empty. Please ask a complete question.",
        }

    query_lower = query.lower()
    for keyword in IRRELEVANT_KEYWORDS:
        if keyword in query_lower:
            return {
                "is_valid_query": False,
                "router_message": "I can only answer questions about orders, returns, refunds, warranties, and product policies.",
            }

    logger.info(f"Router: valid query for tenant={tenant_id}")
    return {
        "is_valid_query": True,
        "router_message": None,
    }