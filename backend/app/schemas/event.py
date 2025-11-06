"""Event validation schemas using Pydantic."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class EventIngest(BaseModel):
    """Single event ingestion schema."""

    event_id: Optional[str] = Field(None, min_length=1, max_length=36, description="Event ID (UUID)")
    event_type: str = Field(..., min_length=1, max_length=50, description="Type of event")
    run_id: str = Field(..., min_length=1, max_length=36, description="Run ID (UUID)")
    run_name: str = Field(..., min_length=1, max_length=255, description="Run name")
    agent_name: str = Field(..., min_length=1, max_length=255, description="Agent name")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    parent_event_id: Optional[str] = Field(None, min_length=1, max_length=36, description="Parent event ID for hierarchical relationships")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event data")

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        """Validate ISO 8601 timestamp format."""
        try:
            # Try parsing the timestamp
            datetime.fromisoformat(v.replace("Z", "+00:00"))
            return v
        except (ValueError, AttributeError):
            raise ValueError("Timestamp must be in ISO 8601 format")

    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "llm_call",
                "run_id": "123e4567-e89b-12d3-a456-426614174000",
                "run_name": "run 1",
                "agent_name": "my_agent",
                "timestamp": "2024-11-04T10:30:00Z",
                "data": {
                    "model": "gpt-4",
                    "tokens_in": 100,
                    "tokens_out": 50,
                    "cost": 0.005,
                },
            }
        }


class EventBatch(BaseModel):
    """Batch of events for ingestion."""

    events: List[EventIngest] = Field(..., min_items=1, max_items=10000, description="List of events")

    @field_validator("events")
    @classmethod
    def validate_batch_size(cls, v: List[EventIngest]) -> List[EventIngest]:
        """Validate batch size."""
        if len(v) == 0:
            raise ValueError("Batch must contain at least 1 event")
        if len(v) > 10000:
            raise ValueError("Batch cannot exceed 10,000 events")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "events": [
                    {
                        "event_type": "agent_start",
                        "run_id": "123e4567-e89b-12d3-a456-426614174000",
                        "run_name": "run 1",
                        "agent_name": "my_agent",
                        "timestamp": "2024-11-04T10:30:00Z",
                        "data": {"input": "What is 2+2?"},
                    },
                    {
                        "event_type": "llm_call",
                        "run_id": "123e4567-e89b-12d3-a456-426614174000",
                        "run_name": "run 1",
                        "agent_name": "my_agent",
                        "timestamp": "2024-11-04T10:30:01Z",
                        "data": {
                            "model": "gpt-4",
                            "tokens_in": 100,
                            "tokens_out": 50,
                        },
                    },
                ]
            }
        }


class EventResponse(BaseModel):
    """Single event response schema."""

    event_id: str
    run_name: str
    agent_name: str
    event_type: str
    timestamp: str
    data: Dict[str, Any]
    created_at: str

    class Config:
        from_attributes = True


class EventListResponse(BaseModel):
    """List of events response schema."""

    events: List[EventResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

    class Config:
        json_schema_extra = {
            "example": {
                "events": [],
                "total": 0,
                "page": 1,
                "page_size": 50,
                "total_pages": 0,
            }
        }
