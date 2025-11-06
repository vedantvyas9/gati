# LangGraph Instrumentation Guide

## Overview

The GATI LangGraph instrumentation provides automatic tracking of graph execution, node runs, and state transitions for LangGraph 1.0+ applications. It captures detailed information about your graph's behavior without modifying your existing code logic.

## Features

- **Graph-Level Tracking**: Tracks complete graph execution with start and end events
- **Node Execution Tracking**: Monitors each node's execution with timing and state information
- **State Diff Calculation**: Automatically calculates what changed in the state after each node
- **Error Handling**: Captures errors without crashing graph execution
- **Async Support**: Full support for both sync and async graphs
- **Context Integration**: Uses RunContextManager for parent-child run relationships
- **Multiple Invocation Methods**: Supports `invoke()`, `stream()`, `ainvoke()`, and `astream()`

## Installation

```bash
pip install gati-sdk langgraph
```

## Quick Start

### Basic Usage

```python
from typing import TypedDict
from langgraph.graph import StateGraph, END
from gati import observe
from gati.instrumentation.langgraph import GatiStateGraphWrapper

# 1. Initialize GATI
observe.init(
    backend_url="http://localhost:8000",
    agent_name="my_agent",
)

# 2. Define your state
class AgentState(TypedDict):
    input: str
    output: str

# 3. Define your nodes
def process_node(state: AgentState) -> AgentState:
    return {"input": state["input"], "output": f"Processed: {state['input']}"}

# 4. Create your graph
graph = StateGraph(AgentState)
graph.add_node("process", process_node)
graph.set_entry_point("process")
graph.add_edge("process", END)

# 5. Wrap with GATI instrumentation
wrapped_graph = GatiStateGraphWrapper(graph)
app = wrapped_graph.compile()

# 6. Use normally - all execution is tracked!
result = app.invoke({"input": "Hello", "output": ""})
```

## What Gets Tracked

### 1. Graph-Level Events

#### AgentStartEvent
Emitted when graph execution begins:
```json
{
  "event_type": "agent_start",
  "run_id": "uuid",
  "input": {"input": "Hello", "output": ""},
  "metadata": {
    "graph_type": "langgraph",
    "method": "invoke"
  }
}
```

#### AgentEndEvent
Emitted when graph execution completes:
```json
{
  "event_type": "agent_end",
  "run_id": "uuid",
  "output": {"input": "Hello", "output": "Processed: Hello"},
  "total_duration_ms": 123.45,
  "status": "completed"
}
```

### 2. Node Execution Events

#### NodeExecutionEvent
Emitted for each node execution:
```json
{
  "event_type": "node_execution",
  "run_id": "uuid",
  "node_name": "process",
  "state_before": {"input": "Hello", "output": ""},
  "state_after": {"input": "Hello", "output": "Processed: Hello"},
  "duration_ms": 12.34,
  "data": {
    "state_diff": {
      "output": {
        "before": "",
        "after": "Processed: Hello"
      }
    },
    "status": "completed"
  }
}
```

## Advanced Usage

### Working with TypedDict States

The instrumentation automatically handles TypedDict states:

```python
from typing import TypedDict, Annotated
import operator

class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    count: int
    result: str

def node_func(state: AgentState) -> AgentState:
    return {
        **state,
        "messages": ["New message"],
        "count": state["count"] + 1,
    }
```

### Working with Dataclass States

Dataclass states are also supported:

```python
from dataclasses import dataclass

@dataclass
class AgentState:
    input: str
    output: str
    count: int = 0

def node_func(state: AgentState) -> AgentState:
    return AgentState(
        input=state.input,
        output=f"Processed: {state.input}",
        count=state.count + 1,
    )
```

### Async Graphs

Full support for async nodes and execution:

```python
async def async_node(state: AgentState) -> AgentState:
    await asyncio.sleep(0.1)
    return {"input": state["input"], "output": "Async result"}

# Create async graph
graph = StateGraph(AgentState)
graph.add_node("async_process", async_node)
graph.set_entry_point("async_process")
graph.add_edge("async_process", END)

# Wrap and compile
wrapped = GatiStateGraphWrapper(graph)
app = wrapped.compile()

# Use async methods
result = await app.ainvoke({"input": "Hello", "output": ""})

# Or stream async
async for chunk in app.astream({"input": "Hello", "output": ""}):
    print(chunk)
```

### Streaming

Track streaming execution:

```python
# Synchronous streaming
for chunk in app.stream({"input": "Hello", "output": ""}):
    print(chunk)

# Async streaming
async for chunk in app.astream({"input": "Hello", "output": ""}):
    print(chunk)
```

### Error Handling

Errors are automatically tracked without crashing execution:

```python
def failing_node(state: AgentState) -> AgentState:
    raise ValueError("Something went wrong!")

# The error will be tracked in NodeExecutionEvent:
{
  "event_type": "node_execution",
  "node_name": "failing_node",
  "data": {
    "error": {
      "type": "ValueError",
      "message": "Something went wrong!"
    },
    "status": "error"
  }
}
```

### Nested Contexts

The instrumentation integrates with GATI's RunContextManager for nested execution:

```python
from gati.core.context import run_context

# Parent context
with run_context() as parent_run_id:
    # Child context (graph execution)
    result = app.invoke({"input": "Hello", "output": ""})
    # Graph events will have parent_run_id in their context
```

## State Diff Calculation

The instrumentation automatically calculates what changed in the state after each node:

### Example 1: Simple Field Change

```python
# Before
{"input": "Hello", "count": 0, "output": ""}

# After
{"input": "Hello", "count": 1, "output": "Processed"}

# Diff
{
  "count": {"before": 0, "after": 1},
  "output": {"before": "", "after": "Processed"}
}
```

### Example 2: List Accumulation

```python
# Before
{"messages": ["Hello"], "count": 1}

# After
{"messages": ["Hello", "World"], "count": 2}

# Diff
{
  "messages": {
    "before": ["Hello"],
    "after": ["Hello", "World"]
  },
  "count": {"before": 1, "after": 2}
}
```

## Configuration

### GATI Initialization Options

```python
observe.init(
    backend_url="http://localhost:8000",  # Required: Your GATI backend URL
    agent_name="my_agent",                # Optional: Agent identifier
    batch_size=100,                       # Optional: Events per batch (default: 100)
    flush_interval=5,                     # Optional: Seconds between flushes (default: 5)
    api_key="your-api-key",              # Optional: API key for authentication
)
```

### Manual Event Flushing

```python
# Force flush all buffered events
observe.flush()

# Graceful shutdown (flushes and closes connections)
observe.shutdown()
```

## Best Practices

### 1. Initialize Early

Initialize GATI before creating your graph:

```python
# ✓ Good
observe.init(backend_url="...")
graph = StateGraph(AgentState)

# ✗ Bad - might miss early events
graph = StateGraph(AgentState)
observe.init(backend_url="...")
```

### 2. Use Context Managers for Cleanup

```python
with observe:
    # Your graph execution
    result = app.invoke(state)
# Automatic shutdown and flush on exit
```

### 3. Wrap Once, Use Many Times

```python
# Wrap during setup
wrapped_graph = GatiStateGraphWrapper(graph)
app = wrapped_graph.compile()

# Reuse the compiled app
for input_data in inputs:
    result = app.invoke(input_data)
```

### 4. Don't Catch Tracking Errors

The instrumentation is designed to never crash your application. Don't wrap tracking in try-except:

```python
# ✓ Good - let the instrumentation handle errors
result = app.invoke(state)

# ✗ Bad - unnecessary
try:
    result = app.invoke(state)
except Exception as e:
    # Tracking errors are already handled internally
    pass
```

## Comparison with LangChain Instrumentation

| Feature | LangChain | LangGraph |
|---------|-----------|-----------|
| Instrumentation Type | Callback Handler | Wrapper Class |
| Auto-injection | ✓ (via `auto_inject=True`) | ✗ (explicit wrapping required) |
| Node Tracking | Chain steps | Graph nodes |
| State Tracking | ✗ | ✓ (with diffs) |
| Streaming | ✓ | ✓ |
| Async Support | ✓ | ✓ |
| Error Tracking | ✓ | ✓ |

## Troubleshooting

### Events Not Appearing in Backend

1. **Check Backend Connection**:
   ```python
   # Test with manual flush
   observe.flush()
   ```

2. **Verify Initialization**:
   ```python
   # Ensure init was called
   if not observe._initialized:
       print("GATI not initialized!")
   ```

3. **Check Backend URL**:
   ```python
   # Print current config
   print(observe._config.backend_url)
   ```

### State Diffs Not Showing

State diffs require comparable before/after states:

```python
# ✓ Good - returns new state
def node(state: AgentState) -> AgentState:
    return {...state, "output": "new"}

# ✗ Bad - mutates state in place (diff may be empty)
def node(state: AgentState) -> AgentState:
    state["output"] = "new"  # Mutation
    return state
```

### Performance Concerns

The instrumentation is designed to be lightweight, but for very high-throughput scenarios:

1. **Increase Batch Size**:
   ```python
   observe.init(batch_size=1000)  # Default: 100
   ```

2. **Increase Flush Interval**:
   ```python
   observe.init(flush_interval=10)  # Default: 5 seconds
   ```

3. **Simplify State Serialization**:
   - Keep state objects simple
   - Avoid deeply nested structures
   - Use primitive types when possible

## API Reference

### GatiStateGraphWrapper

```python
class GatiStateGraphWrapper:
    def __init__(self, graph: StateGraph)
    def compile(self, *args, **kwargs) -> Pregel
```

**Parameters:**
- `graph`: LangGraph StateGraph instance to wrap

**Returns:**
- Instrumented Pregel instance

### instrument_langgraph()

```python
def instrument_langgraph() -> bool
```

Checks if LangGraph is available. Note: Unlike LangChain, LangGraph doesn't support automatic instrumentation via global callbacks.

**Returns:**
- `True` if LangGraph is installed, `False` otherwise

## Examples

See the following files for complete examples:

- `examples/langgraph_example.py` - Basic usage with conditional routing
- `test_langgraph_instrumentation.py` - Comprehensive test suite

## Support

For issues, questions, or contributions:

- GitHub Issues: https://github.com/your-org/gati-sdk/issues
- Documentation: https://docs.gati.ai

## License

MIT License - See LICENSE file for details
