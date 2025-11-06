# LangGraph Instrumentation - Implementation Overview

## Overview

The GATI SDK provides **automatic instrumentation for LangGraph** by monkey-patching the `StateGraph.compile()` method. Once enabled via `observe.init(auto_inject=True)`, all LangGraph graph executions are automatically tracked without any code changes required.

## Features

### 1. Agent-Level Tracking

**What's tracked:**
- ✅ Agent/graph name
- ✅ Run start/end time and total duration
- ✅ Overall execution status (success/error)
- ✅ User input and final output
- ✅ Error messages and stack traces

**Implementation:**
- `AgentStartEvent` created when graph execution begins
- `AgentEndEvent` created when graph execution completes
- Proper context management with `run_context()`

### 2. Node-Level Tracking

**What's tracked:**
- ✅ Node name and execution timing
- ✅ Input & output state (full snapshots)
- ✅ State changes (diffs showing what changed)
- ✅ Node transitions (from → to)
- ✅ Step status (ok/failed)
- ✅ Function/class name executed
- ✅ Node type detection (LLM, tool, subgraph, custom)
- ✅ Errors with stack traces

**Implementation:**
- `NodeExecutionEvent` created for each node execution
- Rich metadata extraction via `_extract_node_metadata()`
- State diffing to track changes
- Nested subgraph tracking

### 3. Integration with LangChain Instrumentation

**What's tracked:**
- ✅ All LLM calls within nodes
- ✅ All tool invocations within nodes
- ✅ Proper parent-child relationships

**Implementation:**
- Relies on LangChain instrumentation (runs automatically)
- Events properly nested under node execution events
- `parent_event_id` propagation ensures proper hierarchy

### 4. Nested Subgraph Support

**What's tracked:**
- ✅ Subgraphs detected and tracked separately
- ✅ Proper nesting depth tracking
- ✅ Parent-child relationships maintained

**Implementation:**
- Subgraph depth tracked via context variable
- Recursive instrumentation for nested graphs
- Proper cleanup after subgraph completion

## Architecture

### Patching Strategy

```python
# Core patching happens in instrument_langgraph()
def instrument_langgraph():
    # Store original compile method
    original_compile = StateGraph.compile

    # Wrap compile to inject instrumentation
    def patched_compile(self, *args, **kwargs):
        # Get original Pregel instance
        pregel = original_compile(self, *args, **kwargs)

        # Wrap stream method to track execution
        pregel.stream = wrapped_stream(pregel.stream)

        return pregel

    StateGraph.compile = patched_compile
```

### Execution Tracking

The instrumentation wraps the `stream()` method (which is called internally by `invoke()`):

```python
def wrapped_stream(original_stream):
    def _stream_wrapper(self, input_data, config=None, **kwargs):
        # Track agent start
        # Execute original stream
        # Track each node execution
        # Track agent end
        ...
    return _stream_wrapper
```

### Context Management

```python
# Prevent duplicate tracking
_in_graph_execution: ContextVar[bool]

# Track nested subgraph depth
_subgraph_depth: ContextVar[int]

# Usage:
with _in_graph_execution.set(True):
    # Execute graph without duplicate tracking
    ...
```

## Usage

### Basic Setup

```python
from gati import observe

# Enable auto-injection (default)
observe.init(
    backend_url="http://localhost:8000",
    agent_name="my_agent",
    auto_inject=True  # Enables both LangChain and LangGraph
)

# Use LangGraph normally - everything is tracked!
from langgraph.graph import StateGraph

graph = StateGraph(MyState)
graph.add_node("node1", node1_func)
graph.add_node("node2", node2_func)
graph.add_edge("node1", "node2")
graph.add_edge("node2", END)

app = graph.compile()
result = app.invoke({"input": "test"})
```

### With LLMs and Tools

```python
from langchain_openai import ChatOpenAI
from langchain.tools import tool

@tool
def search(query: str) -> str:
    """Search for information."""
    return f"Results for {query}"

def llm_node(state):
    llm = ChatOpenAI(model="gpt-3.5-turbo")
    response = llm.invoke(state["messages"])  # ← Tracked by LangChain instrumentation
    return {"messages": [response]}

def tool_node(state):
    result = search.invoke(state["query"])  # ← Tracked by LangChain instrumentation
    return {"result": result}

graph = StateGraph(MyState)
graph.add_node("llm", llm_node)
graph.add_node("tool", tool_node)
graph.add_edge("llm", "tool")

app = graph.compile()
result = app.invoke({"query": "test"})

# Tracks:
# - AgentStartEvent (graph start)
# - NodeExecutionEvent (llm node)
#   - LLMCallEvent (ChatOpenAI call)
# - NodeExecutionEvent (tool node)
#   - ToolCallEvent (search tool call)
# - AgentEndEvent (graph end)
```

### Nested Subgraphs

```python
# Inner graph
inner_graph = StateGraph(InnerState)
inner_graph.add_node("inner_node", inner_func)
inner_app = inner_graph.compile()

# Outer graph that uses inner graph
def outer_node(state):
    result = inner_app.invoke(state)  # ← Nested tracking
    return result

outer_graph = StateGraph(OuterState)
outer_graph.add_node("outer", outer_node)
outer_app = outer_graph.compile()

result = outer_app.invoke({"input": "test"})

# Tracks:
# - AgentStartEvent (outer graph)
# - NodeExecutionEvent (outer node)
#   - AgentStartEvent (inner graph)
#   - NodeExecutionEvent (inner node)
#   - AgentEndEvent (inner graph)
# - AgentEndEvent (outer graph)
```

## Event Structure

### AgentStartEvent (Graph Start)

```json
{
  "event_type": "agent_start",
  "run_id": "uuid-here",
  "event_id": "uuid-here",
  "agent_name": "StateGraph",
  "input": {
    "input": "test query"
  },
  "metadata": {
    "auto_tracked": true,
    "langgraph_execution": true,
    "subgraph_depth": 0
  }
}
```

### NodeExecutionEvent

```json
{
  "event_type": "node_execution",
  "run_id": "uuid-here",
  "event_id": "uuid-here",
  "parent_event_id": "parent-uuid",
  "node_name": "llm_node",
  "state_before": {
    "messages": [],
    "query": "test"
  },
  "state_after": {
    "messages": ["AI response"],
    "query": "test"
  },
  "duration_ms": 234.5,
  "data": {
    "status": "completed",
    "node_metadata": {
      "function_name": "llm_node",
      "module": "my_module",
      "node_type": "custom",
      "is_subgraph": false
    },
    "state_diff": {
      "messages": {
        "before": [],
        "after": ["AI response"]
      }
    },
    "transition": {
      "from": "__start__",
      "to": "llm_node"
    }
  }
}
```

### AgentEndEvent (Graph End)

```json
{
  "event_type": "agent_end",
  "run_id": "uuid-here",
  "event_id": "uuid-here",
  "output": {
    "result": "final output"
  },
  "total_duration_ms": 456.7,
  "metadata": {
    "status": "completed",
    "auto_tracked": true,
    "subgraph_depth": 0
  }
}
```

## Node Type Detection

The instrumentation automatically detects node types:

```python
def _extract_node_metadata(pregel, node_name):
    # Detects:
    # - LLM nodes (checks for LangChain LLM usage)
    # - Tool nodes (checks for tool decorators)
    # - Subgraph nodes (checks for nested Pregel instances)
    # - Custom function nodes
    ...
```

## State Diffing

The instrumentation computes state diffs to show what changed:

```python
# Before state
{"messages": [], "counter": 0}

# After state
{"messages": ["Hello"], "counter": 1}

# Diff
{
  "messages": {
    "before": [],
    "after": ["Hello"]
  },
  "counter": {
    "before": 0,
    "after": 1
  }
}
```

## Implementation Files

### Modified Files

1. **[auto_inject.py](auto_inject.py)**
   - `instrument_langgraph()` - Main entry point
   - `_wrap_pregel_stream()` - Wraps stream method
   - `_extract_node_metadata()` - Extracts node information
   - `_compute_state_diff()` - Computes state changes
   - Context variable management for nested tracking

## Error Handling

All instrumentation code follows these principles:

1. **Never raise exceptions** - All code wrapped in try/except
2. **Graceful degradation** - Missing LangGraph logged, not fatal
3. **Fail-safe fallbacks** - Original methods always callable
4. **Detailed logging** - Debug logs for all failures

Example:
```python
try:
    # Track node execution
    event = NodeExecutionEvent(...)
    observe.track_event(event)
except Exception as e:
    logger.debug(f"Failed to track node execution: {e}")
    # Continue execution without tracking
```

## Performance Impact

The instrumentation is designed to be lightweight:

- **Minimal overhead** - Only metadata extraction and event creation
- **No blocking operations** - All tracking is async/buffered
- **Memory efficient** - State snapshots only for changed values
- **Production ready** - Can be enabled in production

## Integration with LangChain

LangGraph instrumentation works seamlessly with LangChain instrumentation:

```python
# In a LangGraph node
def my_node(state):
    # This LLM call is tracked by LangChain instrumentation
    llm = ChatOpenAI(model="gpt-3.5-turbo")
    response = llm.invoke(state["prompt"])

    # This tool call is tracked by LangChain instrumentation
    tool = get_tool("search")
    result = tool.invoke(state["query"])

    return {"response": response, "result": result}

# The LangGraph instrumentation tracks:
# - Node start/end
# - State changes
#
# The LangChain instrumentation tracks:
# - LLM calls within the node
# - Tool calls within the node
#
# Both are properly nested via parent_event_id
```

## Conclusion

The GATI SDK provides **comprehensive LangGraph instrumentation** with:

✅ **Full graph tracking** - Agent and node-level events
✅ **State tracking** - Before/after snapshots with diffs
✅ **Nested subgraphs** - Proper hierarchy tracking
✅ **LangChain integration** - LLM and tool calls tracked
✅ **Zero code changes** - Automatic instrumentation
✅ **Production ready** - Robust error handling

Simply call `observe.init(auto_inject=True)` and start using LangGraph - everything will be tracked automatically!
