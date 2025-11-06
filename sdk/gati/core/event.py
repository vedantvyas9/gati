"""Event system for tracking agent operations."""
import json
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Any, Dict, Optional


def generate_run_id(agent_name: str = "") -> str:
    """Generate a unique run ID (UUID).

    Args:
        agent_name: Name of the agent (not used for ID generation)

    Returns:
        A unique UUID string
    """
    return str(uuid.uuid4())


def generate_run_name(agent_name: str = "", run_number: Optional[int] = None) -> str:
    """Generate a run name.

    Args:
        agent_name: Name of the agent (used for backend validation)
        run_number: Optional run number. If not provided, backend will auto-assign.

    Returns:
        Run name in format 'run {number}' or temporary placeholder if number not provided
    """
    if run_number is not None:
        return f"run {run_number}"
    # Return a temporary UUID that backend will replace with proper run name
    return f"temp_{uuid.uuid4()}"


@dataclass
class Event:
    """Base event class for tracking agent operations."""
    event_type: str = ""
    run_id: str = ""  # Unique UUID for the run
    run_name: str = ""  # Human-readable run name (e.g., "run 1")
    timestamp: str = field(default="")
    agent_name: str = ""
    event_id: str = field(default="")
    parent_event_id: Optional[str] = field(default=None)
    data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Set timestamp and event_id if not provided."""
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()
        if not self.event_id:
            self.event_id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize event to JSON string."""
        return json.dumps(self.to_dict(), default=str)


@dataclass
class LLMCallEvent(Event):
    """Event for tracking LLM calls."""
    model: str = field(default="")
    prompt: str = field(default="")
    completion: str = field(default="")
    tokens_in: int = field(default=0)
    tokens_out: int = field(default=0)
    latency_ms: float = field(default=0.0)
    cost: float = field(default=0.0)
    system_prompt: str = field(default="")

    def __post_init__(self):
        """Initialize LLM call event."""
        super().__post_init__()
        self.event_type = "llm_call"
        if not self.data:
            self.data = {
                "model": self.model,
                "prompt": self.prompt,
                "completion": self.completion,
                "tokens_in": self.tokens_in,
                "tokens_out": self.tokens_out,
                "latency_ms": self.latency_ms,
                "cost": self.cost,
                "system_prompt": self.system_prompt,
            }


@dataclass
class ToolCallEvent(Event):
    """Event for tracking tool calls."""
    tool_name: str = field(default="")
    input: Dict[str, Any] = field(default_factory=dict)
    output: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = field(default=0.0)

    def __post_init__(self):
        """Initialize tool call event."""
        super().__post_init__()
        self.event_type = "tool_call"
        if not self.data:
            self.data = {
                "tool_name": self.tool_name,
                "input": self.input,
                "output": self.output,
                "latency_ms": self.latency_ms,
            }


@dataclass
class AgentStartEvent(Event):
    """Event for tracking agent start."""
    input: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize agent start event."""
        super().__post_init__()
        self.event_type = "agent_start"
        if not self.data:
            self.data = {
                "input": self.input,
                "metadata": self.metadata,
            }


@dataclass
class AgentEndEvent(Event):
    """Event for tracking agent end."""
    output: Dict[str, Any] = field(default_factory=dict)
    total_duration_ms: float = field(default=0.0)
    total_cost: float = field(default=0.0)

    def __post_init__(self):
        """Initialize agent end event."""
        super().__post_init__()
        self.event_type = "agent_end"
        if not self.data:
            self.data = {
                "output": self.output,
                "total_duration_ms": self.total_duration_ms,
                "total_cost": self.total_cost,
            }


@dataclass
class NodeExecutionEvent(Event):
    """Event for tracking node execution in graph-based agents."""
    node_name: str = field(default="")
    state_before: Dict[str, Any] = field(default_factory=dict)
    state_after: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = field(default=0.0)

    def __post_init__(self):
        """Initialize node execution event."""
        super().__post_init__()
        self.event_type = "node_execution"
        if not self.data:
            self.data = {
                "node_name": self.node_name,
                "state_before": self.state_before,
                "state_after": self.state_after,
                "duration_ms": self.duration_ms,
            }


@dataclass
class StepEvent(Event):
    """Event for tracking individual steps within an agent."""
    step_name: str = field(default="")
    input: Dict[str, Any] = field(default_factory=dict)
    output: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = field(default=0.0)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize step event."""
        super().__post_init__()
        self.event_type = "step"
        if not self.data:
            self.data = {
                "step_name": self.step_name,
                "input": self.input,
                "output": self.output,
                "duration_ms": self.duration_ms,
                "metadata": self.metadata,
            }

