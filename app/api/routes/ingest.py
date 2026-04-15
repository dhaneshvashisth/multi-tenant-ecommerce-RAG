from fastapi import APIRouter, Depends, HTTPException, status
from app.api.dependencies import verify_tenant
from app.schemas.requests import IngestRequest
from app.schemas.responses import IngestResponse
from kafka_workers.producer import publish_ingestion_job
import logging
import os

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/ingest", response_model=IngestResponse, summary="Ingest a policy document for a tenant", tags=["Ingestion"],)
async def ingest_document(request: IngestRequest, tenant_id: str = Depends(verify_tenant),):
    """Publishes a document ingestion job to Kafka. Returns immediately — processing is asynchronous.
    The Kafka consumer handles:
    - PDF/text extraction
    - Chunking
    - Embedding generation
    - Qdrant upsert
    - Audit log
    """
    if not os.path.exists(request.document_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {request.document_path}",
        )

    await publish_ingestion_job(tenant_id, request.document_path)
    logger.info(f"Ingestion job published: tenant={tenant_id} doc={request.document_path}")

    return IngestResponse(
        status="accepted",
        message="Document ingestion job queued successfully",
        tenant_id=tenant_id,
        document_path=request.document_path,
    )