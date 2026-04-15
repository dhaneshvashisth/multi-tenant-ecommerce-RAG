from fastapi import APIRouter, Depends, HTTPException, status
from app.api.dependencies import verify_tenant
from app.schemas.requests import FeedbackRequest
from app.schemas.responses import FeedbackResponse
from kafka_workers.producer import publish_feedback
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    summary="Submit feedback for a RAG response",
    tags=["Feedback"],
)
async def feedback_endpoint(
    request: FeedbackRequest,
    tenant_id: str = Depends(verify_tenant),
):
    """
    Publishes feedback to Kafka feedback topic.
    Returns immediately — DB write is asynchronous.
    Rating: 1 = thumbs up, -1 = thumbs down
    """
    if request.rating not in (1, -1):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Rating must be 1 (thumbs up) or -1 (thumbs down)",
        )

    await publish_feedback(
        tenant_id=tenant_id,
        session_id=request.session_id,
        query=request.query,
        response=request.response,
        rating=request.rating,
        prompt_version=request.prompt_version,
    )
    logger.info(
        f"Feedback published: tenant={tenant_id} "
        f"session={request.session_id} rating={request.rating}"
    )

    return FeedbackResponse(
        status="accepted",
        message="Feedback submitted successfully",
        tenant_id=tenant_id,
        session_id=request.session_id,
        rating=request.rating,
    )