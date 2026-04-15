from fastapi import APIRouter, Depends, HTTPException, status
from app.api.dependencies import verify_tenant
from app.schemas.requests import QueryRequest
from app.schemas.responses import QueryResponse
from app.rag.pipeline import query_rag
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query", response_model=QueryResponse,summary="Query the RAG pipeline for a tenant",tags=["Query"],)
async def query_endpoint( request: QueryRequest, tenant_id: str = Depends(verify_tenant),):
    """ Runs the full RAG pipeline:
    1. Semantic cache check
    2. Conversation memory load
    3. LangGraph: router → retriever → reranker → generator → citations
    4. Cache + memory update
    """
    try:
        result = await query_rag(tenant_id=tenant_id, query=request.query,session_id=request.session_id)
        
        return QueryResponse(**result)
    except Exception as e:
        logger.error(f"Query failed: tenant={tenant_id} error={e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query processing failed: {str(e)}",
        )