"""Agent-related response schemas."""
from typing import Optional

from pydantic import BaseModel


class AgentResponse(BaseModel):
    """Agent response schema."""

    name: str
    description: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class AgentStatsResponse(BaseModel):
    """Agent statistics response."""

    name: str
    description: Optional[str] = None
    total_runs: int = 0
    total_events: int = 0
    total_cost: float = 0.0
    avg_cost: float = 0.0
    created_at: str

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "name": "my_agent",
                "description": "My first agent",
                "total_runs": 42,
                "total_events": 1250,
                "total_cost": 15.75,
                "avg_cost": 0.375,
                "created_at": "2024-11-04T10:00:00Z",
            }
        }
