import asyncio
import sys
import os
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import AsyncOpenAI
from app.core.config import get_settings
from app.db.postgres import init_db_pool, get_pool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()

SCORE_THRESHOLD = 0.0
OPTIMIZATION_MODEL = "gpt-4o-mini"


async def get_low_performing_prompts() -> list[dict]:
    """
    Finds active prompts with avg_feedback_score below threshold.
    Only considers prompts that have received at least 3 feedback events
    to avoid optimizing on too little data.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                pr.id,
                pr.tenant_id,
                pr.version,
                pr.prompt_text,
                pr.avg_feedback_score,
                COUNT(f.id) as feedback_count
            FROM prompt_registry pr
            LEFT JOIN feedback f
                ON f.tenant_id = pr.tenant_id
                AND f.prompt_version = pr.version
            WHERE pr.is_active = TRUE
              AND pr.avg_feedback_score IS NOT NULL
              AND pr.avg_feedback_score <= $1
            GROUP BY pr.id, pr.tenant_id, pr.version, pr.prompt_text, pr.avg_feedback_score
            HAVING COUNT(f.id) >= 3
            """,
            SCORE_THRESHOLD,
        )
    return [dict(r) for r in rows]


async def generate_improved_prompt(
    tenant_id: str,
    current_prompt: str,
    avg_score: float,
    openai_client: AsyncOpenAI,
) -> str:
    """
    Calls GPT-4o-mini to rewrite a low-performing prompt.

    The meta-prompt explains the context and asks the LLM
    to improve the system prompt for better customer support responses.
    """
    meta_prompt = f"""You are a prompt engineering expert specializing in customer support AI systems.

The following system prompt for a {tenant_id} customer support bot has received poor user feedback 
(average rating: {avg_score:.2f} on a scale of -1 to 1, where 1 is positive and -1 is negative).

Current prompt:
---
{current_prompt}
---

Please rewrite this system prompt to:
1. Be more helpful and accurate in answering policy questions
2. Better cite specific policy sections
3. Handle edge cases more gracefully
4. Maintain a professional and empathetic tone
5. Stay strictly within the provided context (no hallucination)

Return ONLY the improved prompt text, nothing else."""

    response = await openai_client.chat.completions.create(
        model=OPTIMIZATION_MODEL,
        messages=[{"role": "user", "content": meta_prompt}],
        max_tokens=600,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


async def insert_new_prompt_version(
    tenant_id: str,
    new_prompt_text: str,
    old_version: int,
) -> None:
    """
    Deactivates the current prompt and inserts a new version.
    The generator node reads is_active=TRUE, so it automatically
    switches to the new prompt on the next query.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                UPDATE prompt_registry
                SET is_active = FALSE
                WHERE tenant_id = $1 AND is_active = TRUE
                """,
                tenant_id,
            )

            new_version = old_version + 1
            await conn.execute(
                """
                INSERT INTO prompt_registry
                    (tenant_id, version, prompt_text, is_active)
                VALUES ($1, $2, $3, TRUE)
                """,
                tenant_id,
                new_version,
                new_prompt_text,
            )
            logger.info(
                f"New prompt inserted: tenant={tenant_id} "
                f"version={new_version}"
            )


async def run_optimization() -> None:
    """
    Main optimization loop.
    Finds low-performing prompts, rewrites them, inserts new versions.
    """
    await init_db_pool()
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

    logger.info("Starting prompt optimization job...")
    low_performers = await get_low_performing_prompts()

    if not low_performers:
        logger.info("No prompts below threshold. Nothing to optimize.")
        return

    logger.info(f"Found {len(low_performers)} prompt(s) to optimize")

    for prompt in low_performers:
        tenant_id = prompt["tenant_id"]
        current_version = prompt["version"]
        avg_score = prompt["avg_feedback_score"]

        logger.info(
            f"Optimizing: tenant={tenant_id} "
            f"version={current_version} avg_score={avg_score:.3f}"
        )

        new_prompt = await generate_improved_prompt(
            tenant_id,
            prompt["prompt_text"],
            avg_score,
            openai_client,
        )

        await insert_new_prompt_version(tenant_id, new_prompt, current_version)

        logger.info(f"Optimization complete for tenant={tenant_id}")

    logger.info("Prompt optimization job finished.")


if __name__ == "__main__":
    asyncio.run(run_optimization())