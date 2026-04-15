from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    document_path: str = Field(...,description="Path to the document inside the container",example="/app/data/amazon/return_policy.txt")


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=5,
        description="Customer support question",
        example="What is the return window for electronics?"
    )
    session_id: str = Field(
        ...,
        description="Unique session identifier for conversation memory",
        example="session-abc-123"
    )


class FeedbackRequest(BaseModel):
    session_id: str
    query: str
    response: str
    rating: int = Field(
        ...,
        description="1 for thumbs up, -1 for thumbs down",
        ge=-1,
        le=1,
    )
    prompt_version: int = Field(default=1)