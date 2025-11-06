"""Run-related response schemas."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RunResponse(BaseModel):
    """Run response schema."""

    run_name: str
    agent_name: str
    environment: Optional[str] = None
    status: Optional[str] = None
    total_duration_ms: Optional[float] = None
    total_cost: Optional[float] = None
    tokens_in: Optional[float] = None
    tokens_out: Optional[float] = None
    created_at: str

    class Config:
        from_attributes = True


class RunDetailResponse(BaseModel):
    """Detailed run response with events."""

    run_name: str
    agent_name: str
    environment: Optional[str] = None
    status: Optional[str] = None
    total_duration_ms: Optional[float] = None
    total_cost: Optional[float] = None
    tokens_in: Optional[float] = None
    tokens_out: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: str
    event_count: int = 0

    class Config:
        from_attributes = True


class RunTimelineEvent(BaseModel):
    """Event in run timeline."""

    event_id: str
    event_type: str
    timestamp: str
    data: Dict[str, Any]

    class Config:
        from_attributes = True


class RunTimelineResponse(BaseModel):
    """Run timeline response with events in chronological order."""

    run_name: str
    agent_name: str
    status: Optional[str] = None
    total_duration_ms: Optional[float] = None
    created_at: str
    events: List[RunTimelineEvent] = []

    class Config:
        json_schema_extra = {
            "example": {
                "run_name": "run 1",
                "agent_name": "my_agent",
                "status": "completed",
                "total_duration_ms": 5000,
                "created_at": "2024-11-04T10:00:00Z",
                "events": [
                    {
                        "event_id": "event-1",
                        "event_type": "agent_start",
                        "timestamp": "2024-11-04T10:00:00Z",
                        "data": {"input": "What is 2+2?"},
                    },
                    {
                        "event_id": "event-2",
                        "event_type": "llm_call",
                        "timestamp": "2024-11-04T10:00:01Z",
                        "data": {
                            "model": "gpt-4",
                            "tokens_in": 100,
                            "tokens_out": 50,
                        },
                    },
                ],
            }
        }


class RunUpdateRequest(BaseModel):
    """Request schema for updating run name."""

    new_run_name: str = Field(..., min_length=1, max_length=255, description="New run name")

    class Config:
        json_schema_extra = {
            "example": {
                "new_run_name": "run 5"
            }
        }
