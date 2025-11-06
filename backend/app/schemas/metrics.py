"""Metrics-related response schemas."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TopAgentByCost(BaseModel):
    """Top agent by cost metric."""

    agent_name: str
    cost: float


class TopAgentByRuns(BaseModel):
    """Top agent by runs metric."""

    agent_name: str
    runs: int


class MetricSummary(BaseModel):
    """Individual metric summary."""

    name: str
    value: float
    unit: str

    class Config:
        json_schema_extra = {
            "example": {
                "name": "total_cost",
                "value": 125.50,
                "unit": "USD",
            }
        }


class AgentMetricsResponse(BaseModel):
    """Agent-level metrics response."""

    agent_name: str
    total_runs: int
    total_events: int
    total_cost: float
    avg_cost_per_run: float
    avg_tokens_in: float
    avg_tokens_out: float
    avg_duration_ms: float
    total_tokens_in: float
    total_tokens_out: float
    total_duration_ms: float

    class Config:
        json_schema_extra = {
            "example": {
                "agent_name": "my_agent",
                "total_runs": 42,
                "total_events": 1250,
                "total_cost": 15.75,
                "avg_cost_per_run": 0.375,
                "avg_tokens_in": 500.0,
                "avg_tokens_out": 250.0,
                "avg_duration_ms": 2500.0,
                "total_tokens_in": 21000.0,
                "total_tokens_out": 10500.0,
                "total_duration_ms": 105000.0,
            }
        }


class GlobalMetricsResponse(BaseModel):
    """Global metrics across all agents."""

    total_agents: int
    total_runs: int
    total_events: int
    total_cost: float
    avg_cost_per_run: float
    avg_tokens_in_per_run: float
    avg_tokens_out_per_run: float
    total_tokens_in: float
    total_tokens_out: float
    total_duration_hours: float
    top_agents_by_cost: List[TopAgentByCost] = Field(default_factory=list)
    top_agents_by_runs: List[TopAgentByRuns] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "total_agents": 5,
                "total_runs": 200,
                "total_events": 8500,
                "total_cost": 127.50,
                "avg_cost_per_run": 0.6375,
                "avg_tokens_in_per_run": 750.0,
                "avg_tokens_out_per_run": 375.0,
                "total_tokens_in": 150000.0,
                "total_tokens_out": 75000.0,
                "total_duration_hours": 24.5,
                "top_agents_by_cost": [
                    {"agent_name": "agent_1", "cost": 50.0},
                    {"agent_name": "agent_2", "cost": 35.0},
                ],
                "top_agents_by_runs": [
                    {"agent_name": "agent_1", "runs": 80},
                    {"agent_name": "agent_2", "runs": 70},
                ],
            }
        }


class CostTimestampData(BaseModel):
    """Cost data with timestamp for charting."""

    timestamp: str
    cost: float
    cumulative_cost: float


class TokensTimestampData(BaseModel):
    """Token data with timestamp for charting."""

    timestamp: str
    tokens_in: float
    tokens_out: float
    cumulative_tokens_in: float
    cumulative_tokens_out: float


class AgentComparisonData(BaseModel):
    """Agent comparison data for charts."""

    agent_name: str
    runs: int
    cost: float
    avg_cost_per_run: float
    total_tokens: float


class ExecutionTreeNodeResponse(BaseModel):
    """Execution tree node response with hierarchical structure."""

    event_id: str
    event_type: str
    timestamp: str
    data: Dict[str, Any]
    parent_event_id: Optional[str] = None
    latency_ms: Optional[float] = None
    cost: Optional[float] = None
    tokens_in: Optional[float] = None
    tokens_out: Optional[float] = None
    children: List["ExecutionTreeNodeResponse"] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "event-1",
                "event_type": "agent_start",
                "timestamp": "2024-11-04T10:00:00Z",
                "data": {"input": "What is 2+2?"},
                "parent_event_id": None,
                "latency_ms": 5000.0,
                "cost": 0.005,
                "children": [
                    {
                        "event_id": "event-2",
                        "event_type": "llm_call",
                        "timestamp": "2024-11-04T10:00:01Z",
                        "data": {"model": "gpt-4"},
                        "parent_event_id": "event-1",
                        "latency_ms": 4000.0,
                        "cost": 0.003,
                        "children": [],
                    }
                ],
            }
        }


class ExecutionTraceResponse(BaseModel):
    """Complete execution trace with hierarchical events."""

    run_name: str
    agent_name: str
    total_cost: float
    total_duration_ms: float
    total_tokens_in: float
    total_tokens_out: float
    execution_tree: List[ExecutionTreeNodeResponse] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "run_name": "run 1",
                "agent_name": "my_agent",
                "total_cost": 0.010,
                "total_duration_ms": 5000.0,
                "total_tokens_in": 500,
                "total_tokens_out": 250,
                "execution_tree": [],
            }
        }


# Update forward references for recursive model
ExecutionTreeNodeResponse.model_rebuild()
