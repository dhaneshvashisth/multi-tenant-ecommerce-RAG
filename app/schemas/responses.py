from pydantic import BaseModel
from typing import Optional


class IngestResponse(BaseModel):
    status: str
    message: str
    tenant_id: str
    document_path: str

class CitationItem(BaseModel):
    chunk_index: int
    document_name: str
    text_snippet: str

    rerank_score: float


class QueryResponse(BaseModel):
    tenant_id: str
    query: str
    session_id: str
    final_response: str
    citations: list[CitationItem]

    cache_hit: bool
    similarity_score: Optional[float] = None

class FeedbackResponse(BaseModel):
    status: str
    message: str
    tenant_id: str
    session_id: str
    
    rating: int


class ServiceStatus(BaseModel):
    status: str
    postgres: str
    qdrant: str
    redis: str
    kafka: str
class HealthResponse(BaseModel):
    status: str
    app_env: str
    version: str
    services: ServiceStatus