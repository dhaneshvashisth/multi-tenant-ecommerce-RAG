import logging
from openai import AsyncOpenAI
from app.rag.state import RAGState
from app.db.prompt_registry import get_active_prompt
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

LLM_MODEL = "gpt-4o-mini"
MAX_TOKENS = 512


async def generator_node(state: RAGState) -> dict:
    """
    Node 4: LLM response generation.

    Steps:
    1. Fetch active system prompt from Postgres prompt registry
    2. Build context string from reranked chunks
    3. Inject conversation history for multi-turn memory (Phase 4)
    4. Call GPT-4o-mini
    5. Return raw response

    Why prompt from registry (not hardcoded):
    - Phase 5 feedback loop rewrites prompts based on ratings
    - Generator always reads latest active version
    - Zero code changes needed to improve response quality
    """
    if not state["is_valid_query"]:
        return {
            "system_prompt": "",
            "raw_response": state.get("router_message", "Invalid query."),
        }

    tenant_id = state["tenant_id"]
    query = state["query"]
    reranked_chunks = state["reranked_chunks"]
    conversation_history = state.get("conversation_history", [])

    system_prompt = await get_active_prompt(tenant_id)

    if reranked_chunks:
        context_parts = []
        for i, chunk in enumerate(reranked_chunks, 1):
            context_parts.append(
                f"[Source {i} - {chunk['document_name']}]\n{chunk['text']}"
            )
        context = "\n\n".join(context_parts)
    else:
        context = "No relevant policy information found."

    messages = [{"role": "system", "content": system_prompt}]

    for turn in conversation_history[-4:]: 
        messages.append(turn)

    messages.append({
        "role": "user",
        "content": f"Context:\n{context}\n\nQuestion: {query}",
    })

    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        max_tokens=MAX_TOKENS,
        temperature=0.1, 
    )

    raw_response = response.choices[0].message.content
    logger.info(f"Generator: response generated for tenant={tenant_id}")

    return {
        "system_prompt": system_prompt,
        "raw_response": raw_response,
    }