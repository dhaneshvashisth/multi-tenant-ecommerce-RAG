import logging
from app.db.postgres import get_pool

logger = logging.getLogger(__name__)

DEFAULT_PROMPTS = {
    "amazon": """You are Amazon's customer support assistant. 
Answer customer questions accurately using only the provided policy context.
Always cite the specific policy section you are referencing.
If the answer is not in the context, say: "I don't have information about that in our current policies. Please contact Amazon support directly."
Be concise, professional, and helpful.""",

    "flipkart": """You are Flipkart's customer support assistant.
Answer customer questions accurately using only the provided policy context.
Always cite the specific policy section you are referencing.
If the answer is not in the context, say: "I don't have information about that in our current policies. Please contact Flipkart support directly."
Be concise, professional, and helpful.""",

    "myntra": """You are Myntra's customer support assistant.
Answer customer questions accurately using only the provided policy context.
Always cite the specific policy section you are referencing.
If the answer is not in the context, say: "I don't have information about that in our current policies. Please contact Myntra support directly."
Be concise, professional, and helpful.""",
}


async def seed_default_prompts() -> None:
    """
    Inserts default prompts for all tenants if they don't exist.
    Called on app startup. Safe to run multiple times.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        for tenant_id, prompt_text in DEFAULT_PROMPTS.items():
            existing = await conn.fetchrow(
                """
                SELECT id FROM prompt_registry
                WHERE tenant_id = $1 AND is_active = TRUE
                """,
                tenant_id,
            )
            if not existing:
                await conn.execute(
                    """
                    INSERT INTO prompt_registry
                        (tenant_id, version, prompt_text, is_active)
                    VALUES ($1, 1, $2, TRUE)
                    """,
                    tenant_id,
                    prompt_text,
                )
                logger.info(f"Seeded default prompt for tenant: {tenant_id}")
            else:
                logger.info(f"Prompt already exists for tenant: {tenant_id}")


async def get_active_prompt(tenant_id: str) -> str:
    """
    Fetches the currently active prompt for a tenant.
    Falls back to default if none found in DB.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT prompt_text FROM prompt_registry
            WHERE tenant_id = $1 AND is_active = TRUE
            ORDER BY version DESC
            LIMIT 1
            """,
            tenant_id,
        )
    if row:
        return row["prompt_text"]
    return DEFAULT_PROMPTS.get(tenant_id, "You are a helpful customer support assistant.")