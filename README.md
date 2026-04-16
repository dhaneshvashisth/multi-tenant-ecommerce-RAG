# Multi-Tenant E-commerce Support RAG

> A production-grade, multi-tenant customer support system powered by LangGraph, Qdrant, Kafka, Redis, and PostgreSQL — serving Amazon, Flipkart, and Myntra from a single deployment with zero data leakage between tenants.

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-green)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.1.19-purple)](https://langchain-ai.github.io/langgraph)
[![Qdrant](https://img.shields.io/badge/Qdrant-1.9.2-red)](https://qdrant.tech)
[![Kafka](https://img.shields.io/badge/Apache%20Kafka-7.5.0-black)](https://kafka.apache.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue)](https://docker.com)

---

## The Problem

E-commerce companies receive thousands of customer support tickets daily — about returns, refunds, warranties, and product issues. Support agents waste hours searching through policy PDFs and knowledge bases. Every company has different policies. None of them will share data with competitors.

## The Solution

One AI-powered support system that:

- **Answers in under 2 seconds** with accurate, cited policy responses
- **Enforces hard tenant isolation** — Amazon's data never touches Flipkart's index
- **Learns from feedback** — thumbs up/down drives automatic prompt optimization
- **Remembers conversation context** across multi-turn support sessions
- **Ingests policy updates** asynchronously without downtime

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                             │
│              Streamlit UI  ·  FastAPI Swagger                   │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                     FASTAPI LAYER                               │
│   POST /api/v1/query  ·  /ingest  ·  /feedback  ·  GET /health │
│              Tenant Auth (X-Tenant-ID + X-API-Key)              │
└──────┬──────────────────────────────────────┬───────────────────┘
       │                                      │
┌──────▼──────────────┐              ┌────────▼──────────────────┐
│   SEMANTIC CACHE    │              │     KAFKA PRODUCER        │
│   Redis cosine sim  │              │  document_ingestion topic  │
│   threshold: 0.92   │              │  user_feedback topic       │
│   TTL: 1 hour       │              └────────┬──────────────────┘
└──────┬──────────────┘                       │
       │ cache miss                  ┌─────────▼──────────────────┐
┌──────▼──────────────────────────┐  │    KAFKA CONSUMERS         │
│     LANGGRAPH 5-NODE PIPELINE   │  │                            │
│                                 │  │  ingestion_consumer:       │
│  ┌─────────────────────────┐    │  │  PDF → chunks → embeddings │
│  │ Node 1: Router          │    │  │  → Qdrant upsert           │
│  │ Validates query+tenant  │    │  │  → PostgreSQL audit log    │
│  └───────────┬─────────────┘    │  │                            │
│              │                  │  │  feedback_consumer:        │
│  ┌───────────▼─────────────┐    │  │  rating → PostgreSQL       │
│  │ Node 2: Retriever       │    │  │  → avg_score update        │
│  │ Qdrant tenant search    │    │  └────────────────────────────┘
│  │ top-10 candidates       │    │
│  └───────────┬─────────────┘    │  ┌─────────────────────────────┐
│              │                  │  │     STORAGE LAYER           │
│  ┌───────────▼─────────────┐    │  │                             │
│  │ Node 3: Reranker        │    │  │  Qdrant:                    │
│  │ FlashRank cross-encoder │    │  │  amazon_policies collection │
│  │ top-3 from top-10       │    │  │  flipkart_policies          │
│  └───────────┬─────────────┘    │  │  myntra_policies            │
│              │                  │  │                             │
│  ┌───────────▼─────────────┐    │  │  PostgreSQL:                │
│  │ Node 4: Generator       │    │  │  prompt_registry            │
│  │ GPT-4o-mini             │    │  │  feedback                   │
│  │ Prompt from registry    │    │  │  ingestion_audit            │
│  └───────────┬─────────────┘    │  │  ragas_eval_results         │
│              │                  │  │                             │
│  ┌───────────▼─────────────┐    │  │  Redis:                     │
│  │ Node 5: Citation Builder│    │  │  semantic_cache:*           │
│  │ Source attribution      │    │  │  conversation:*             │
│  └─────────────────────────┘    │  └─────────────────────────────┘
└─────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| API Framework | FastAPI 0.111 + asyncpg | Non-blocking REST endpoints |
| RAG Orchestration | LangGraph 0.1.19 | Stateful 5-node pipeline |
| Vector Database | Qdrant 1.9.2 | Tenant-isolated semantic search |
| Embeddings | OpenAI text-embedding-3-small | 1536-dim query + document vectors |
| LLM | OpenAI GPT-4o-mini | Response generation |
| Reranker | FlashRank (ms-marco-MiniLM-L-12-v2) | Local cross-encoder reranking |
| Message Queue | Apache Kafka 7.5.0 | Async ingestion + feedback pipeline |
| Semantic Cache | Redis 7.2 | Cosine similarity query cache |
| Conversation Memory | Redis 7.2 | Per-session multi-turn memory |
| Metadata Store | PostgreSQL 16 | Prompts, feedback, audit logs |
| Evaluation | RAGAS 0.1.9 | Faithfulness + answer relevancy |
| Frontend | Streamlit 1.35.0 | Multi-tenant demo UI |
| Infrastructure | Docker Compose | 9-container orchestration |

---

## Key Engineering Decisions

### 1. Separate Qdrant Collections per Tenant (not metadata filtering)
Metadata filtering still scans a shared index — a single misconfigured filter leaks data across tenants. Separate collections provide hard isolation at the storage layer. Amazon's vectors are physically unreachable from Flipkart's query path.

### 2. Kafka for Ingestion and Feedback (not synchronous DB writes)
The API must remain non-blocking. PDF extraction + embedding generation can take 10–30 seconds per document. Kafka decouples the HTTP response from the processing work. If a consumer crashes, messages persist in Kafka and are reprocessed on restart — zero data loss.

### 3. Two-Stage Retrieval: Vector Search + Cross-Encoder Reranking
Vector similarity finds semantically similar text but not necessarily relevant text. FlashRank's cross-encoder jointly encodes the query and each candidate document together, producing far more accurate relevance scores. Retrieval fetches top-10; reranker selects top-3. This is the production RAG pattern.

### 4. Semantic Cache over Exact-Match Cache
"What is the return policy?" and "How do I return something?" are the same question. An exact-match cache misses both after the first. Cosine similarity at 0.92 threshold catches paraphrases while blocking false positives. Cache hits return in ~50ms vs ~2s for full pipeline.

### 5. Feedback-Driven Prompt Versioning
Prompts are configuration, not code. The feedback loop rewrites prompts based on user ratings without any code deployment. The generator always reads `is_active=TRUE` from the prompt registry — switching to an improved prompt is a single UPDATE query.

---

## Project Structure

```
multi-tenant-rag/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── ingest.py           # POST /api/v1/ingest
│   │   │   ├── query.py            # POST /api/v1/query
│   │   │   ├── feedback.py         # POST /api/v1/feedback
│   │   │   └── health.py           # GET /health (per-service status)
│   │   └── dependencies.py         # Tenant auth via API key headers
│   ├── core/
│   │   ├── config.py               # Pydantic-settings, env var parsing
│   │   ├── semantic_cache.py       # Redis cosine similarity cache
│   │   └── conversation_memory.py  # Redis per-session memory
│   ├── db/
│   │   ├── postgres.py             # asyncpg pool (min=2, max=10)
│   │   ├── qdrant.py               # Async Qdrant client + collection mgmt
│   │   ├── redis_client.py         # Async Redis client
│   │   ├── prompt_registry.py      # Prompt versioning + seeder
│   │   └── schema.sql              # Auto-applied on startup
│   ├── rag/
│   │   ├── nodes/
│   │   │   ├── router.py           # Query validation + tenant check
│   │   │   ├── retriever.py        # Qdrant top-10 semantic search
│   │   │   ├── reranker.py         # FlashRank cross-encoder top-3
│   │   │   ├── generator.py        # GPT-4o-mini + prompt registry
│   │   │   └── citation_builder.py # Source attribution
│   │   ├── graph.py                # LangGraph StateGraph definition
│   │   ├── pipeline.py             # Cache + memory + graph orchestration
│   │   └── state.py                # RAGState TypedDict
│   └── schemas/
│       ├── requests.py             # Pydantic request models
│       └── responses.py            # Pydantic response models
├── kafka_workers/
│   ├── producer.py                 # Ingestion + feedback publishers
│   ├── ingestion_consumer.py       # PDF → embed → Qdrant consumer
│   └── feedback_consumer.py        # Rating → PostgreSQL consumer
├── streamlit_app/
│   └── app.py                      # Multi-tenant chat UI
├── scripts/
│   ├── prompt_optimizer.py         # Feedback-driven prompt rewriter
│   ├── ragas_eval.py               # RAGAS evaluation runner
│   ├── test_ingestion.py
│   ├── test_query.py
│   ├── test_cache_memory.py
│   └── test_feedback.py
├── data/
│   ├── amazon/return_policy.txt
│   ├── flipkart/return_policy.txt
│   └── myntra/return_policy.txt
├── docker-compose.yml
├── Dockerfile
├── Dockerfile.streamlit
├── requirements.txt
└── .env.example
```

---

## Setup & Running

### Prerequisites
- Docker Desktop (running)
- OpenAI API key

### 1. Clone

```bash
git clone https://github.com/YOUR_USERNAME/multi-tenant-rag.git
cd multi-tenant-rag
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set OPENAI_API_KEY
```

### 3. Start all services

```bash
docker compose up --build
```

First run pulls all images and downloads the FlashRank model (~90 seconds). Subsequent starts take ~30 seconds.

### 4. Ingest sample policy documents

```bash
# Amazon
docker exec -it api python -c "import asyncio; from kafka_workers.producer import publish_ingestion_job; asyncio.run(publish_ingestion_job('amazon', '/app/data/amazon/return_policy.txt'))"

# Flipkart
docker exec -it api python -c "import asyncio; from kafka_workers.producer import publish_ingestion_job; asyncio.run(publish_ingestion_job('flipkart', '/app/data/flipkart/return_policy.txt'))"

# Myntra
docker exec -it api python -c "import asyncio; from kafka_workers.producer import publish_ingestion_job; asyncio.run(publish_ingestion_job('myntra', '/app/data/myntra/return_policy.txt'))"
```

### 5. Open interfaces

| Interface | URL |
|---|---|
| Streamlit UI | http://localhost:8501 |
| FastAPI Swagger | http://localhost:8000/docs |
| Qdrant Dashboard | http://localhost:6333/dashboard |

---

## API Reference

All endpoints except `/health` require:

```
X-Tenant-ID:  amazon | flipkart | myntra
X-API-Key:    amazon-key-123 | flipkart-key-456 | myntra-key-789
Content-Type: application/json
```

### POST /api/v1/ingest

Queue a policy document for async processing.

```json
Request:  { "document_path": "/app/data/amazon/return_policy.txt" }
Response: { "status": "accepted", "message": "...", "tenant_id": "amazon", "document_path": "..." }
```

### POST /api/v1/query

Run the full RAG pipeline.

```json
Request:  { "query": "What is the return window for electronics?", "session_id": "abc-123" }
Response: {
  "tenant_id": "amazon",
  "final_response": "The return window for electronics is 15 days...",
  "citations": [{ "document_name": "return_policy.txt", "rerank_score": 0.9445, "text_snippet": "..." }],
  "cache_hit": false,
  "similarity_score": null
}
```

### POST /api/v1/feedback

Submit a rating for a response.

```json
Request:  { "session_id": "abc-123", "query": "...", "response": "...", "rating": 1 }
Response: { "status": "accepted", "rating": 1 }
```

### GET /health

```json
Response: {
  "status": "healthy",
  "services": {
    "postgres": "healthy", "qdrant": "healthy",
    "redis": "healthy",   "kafka": "healthy"
  }
}
```

---

## Tenant Credentials

| Tenant | X-Tenant-ID | X-API-Key |
|---|---|---|
| Amazon | `amazon` | `amazon-key-123` |
| Flipkart | `flipkart` | `flipkart-key-456` |
| Myntra | `myntra` | `myntra-key-789` |

---

## Evaluation

```bash
# Run RAGAS evaluation (faithfulness + answer relevancy)
docker exec -it api python scripts/ragas_eval.py

# Run prompt optimization (rewrites low-scoring prompts)
docker exec -it api python scripts/prompt_optimizer.py
```

RAGAS scores are saved to the `ragas_eval_results` table in PostgreSQL.

---

## Docker Services

| Container | Image | Purpose | Port |
|---|---|---|---|
| api | local build | FastAPI application | 8000 |
| streamlit | local build | Streamlit frontend | 8501 |
| qdrant | qdrant/qdrant:v1.9.2 | Vector database | 6333 |
| postgres | postgres:16 | Metadata + feedback store | 5432 |
| redis | redis:7.2-alpine | Cache + memory | 6379 |
| kafka | confluentinc/cp-kafka:7.5.0 | Message broker | 29092 |
| zookeeper | confluentinc/cp-zookeeper:7.5.0 | Kafka coordination | 2181 |
| ingestion_consumer | local build | Document processing worker | — |
| feedback_consumer | local build | Feedback storage worker | — |

---

## License

MIT