import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision
from app.db.postgres import init_db_pool, get_pool
from app.db.qdrant import init_qdrant_client
from app.db.redis_client import init_redis_client
from app.db.prompt_registry import seed_default_prompts
from app.rag.pipeline import query_rag
import logging

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

TEST_QUESTIONS = {
    "amazon": [
        "What is the return window for electronics?",
        "How long does a refund take to process?",
        "What items cannot be returned?",
        "What should I do if I receive a damaged item?",
        "Does Amazon offer a warranty on its products?",
    ],
    "flipkart": [
        "What is the return window for Flipkart orders?",
        "How long does a Flipkart refund take?",
        "Can I exchange a product on Flipkart?",
        "What is Flipkart's warranty policy?",
        "How does Flipkart handle fashion returns?",
    ],
}


async def run_eval_for_tenant(tenant_id: str) -> dict:
    questions = TEST_QUESTIONS.get(tenant_id, [])
    if not questions:
        return {}

    print(f"\nEvaluating tenant: {tenant_id} ({len(questions)} questions)")

    eval_data = {
        "question": [],
        "answer": [],
        "contexts": [],
        "ground_truth": [],
    }

    for i, question in enumerate(questions):
        print(f"  [{i+1}/{len(questions)}] {question[:60]}")
        result = await query_rag(
            tenant_id=tenant_id,
            query=question,
            session_id=f"ragas-eval-{tenant_id}-{i}",
        )
        eval_data["question"].append(question)
        eval_data["answer"].append(result["final_response"])
        eval_data["contexts"].append(
            [c["text_snippet"] for c in result["citations"]]
        )

        eval_data["ground_truth"].append("")

    dataset = Dataset.from_dict(eval_data)
    scores = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy],
    )

    return {
        "tenant_id": tenant_id,
        "faithfulness": round(scores["faithfulness"], 4),
        "answer_relevancy": round(scores["answer_relevancy"], 4),
        "question_count": len(questions),
    }


async def save_eval_results(results: list[dict]) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        # Create eval results table if not exists
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS ragas_eval_results (
                id SERIAL PRIMARY KEY,
                tenant_id VARCHAR(50),
                faithfulness FLOAT,
                answer_relevancy FLOAT,
                question_count INTEGER,
                evaluated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        for r in results:
            await conn.execute(
                """
                INSERT INTO ragas_eval_results
                    (tenant_id, faithfulness, answer_relevancy, question_count)
                VALUES ($1, $2, $3, $4)
                """,
                r["tenant_id"],
                r["faithfulness"],
                r["answer_relevancy"],
                r["question_count"],
            )
    print("\nEval results saved to PostgreSQL")


async def main():
    await init_db_pool()
    await init_qdrant_client()
    await init_redis_client()
    await seed_default_prompts()

    results = []
    for tenant_id in ["amazon", "flipkart"]:
        result = await run_eval_for_tenant(tenant_id)
        if result:
            results.append(result)

    print("\n=== RAGAS Evaluation Results ===")
    for r in results:
        print(f"\nTenant: {r['tenant_id']}")
        print(f"  Faithfulness:      {r['faithfulness']}")
        print(f"  Answer Relevancy:  {r['answer_relevancy']}")
        print(f"  Questions tested:  {r['question_count']}")

    await save_eval_results(results)


asyncio.run(main())