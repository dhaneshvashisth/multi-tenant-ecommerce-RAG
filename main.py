from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from contextlib import asynccontextmanager
from app.db.postgres import init_db_pool, close_db_pool
from app.db.qdrant import init_qdrant_client, close_qdrant_client
from app.db.prompt_registry import seed_default_prompts

from app.api.routes import ingest, query, feedback, health

from app.db.redis_client import init_redis_client, close_redis_client



settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db_pool()
    await init_qdrant_client()
    await seed_default_prompts()
    await init_redis_client()

    yield
    
    await close_db_pool()
    await close_qdrant_client()
    await close_redis_client()

app = FastAPI(
    title="Multi-Tenant E-commerce Support RAG",
    description="Production-grade RAG system serving Amazon, Flipkart, and Myntra support bots from a single deployment.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(health.router)
app.include_router(ingest.router, prefix="/api/v1")
app.include_router(query.router, prefix="/api/v1")
app.include_router(feedback.router, prefix="/api/v1")

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "app_env": settings.app_env,
        "version": "1.0.0",
    }


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Multi-Tenant RAG API",
        "docs": "/docs",
    }