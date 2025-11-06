# LangGraph Automatic Instrumentation - Implementation Summary

## Overview

Comprehensive automatic instrumentation for LangGraph graphs has been implemented in the GATI observability SDK. The implementation provides complete tracking of graph execution, node-level operations, LLM/tool calls, nested subgraphs, and rich metadata.

## Implementation Location

**File**: [`sdk/gati/instrumentation/langgraph/auto_inject.py`](sdk/gati/instrumentation/langgraph/auto_inject.py)

## Features Implemented

### 1. ✅ LLM and Tool Call Tracking

**Implementation**: Lines 309-317, 504-512

- Automatically injects LangChain callbacks (`observe.get_callbacks()`) into the graph config
- All LLM calls made within nodes are tracked via `GatiLangChainCallback`
- All tool invocations are captured with input/output/latency
- Works seamlessly with existing LangChain instrumentation

**Key Code**:
```python
# Add GATI callbacks if not already present
if not config.get("callbacks"):
    gati_callbacks = observe.get_callbacks()
    if gati_callbacks:
        config["callbacks"] = gati_callbacks
```

### 2. ✅ Run ID and Parent Event ID Propagation

**Implementation**: Lines 302-340, 497-535

- Creates proper run context with `run_context(parent_id=parent_run_id)`
- Propagates `run_id` from graph → node → LLM/tool calls
- Sets `parent_event_id` at each level for complete event hierarchy
- Graph start event is parent of all node events
- Node events are parents of nested LLM/tool calls

**Event Hierarchy**:
```
AgentStartEvent (graph_run_id)
├── NodeExecutionEvent (node1, parent: graph_event_id)
│   ├── LLMCallEvent (parent: node1_event_id)
│   └── ToolCallEvent (parent: node1_event_id)
├── NodeExecutionEvent (node2, parent: graph_event_id)
│   └── LLMCallEvent (parent: node2_event_id)
└── AgentEndEvent (parent: graph_event_id)
```

### 3. ✅ Nested Subgraph Support

**Implementation**: Lines 82, 290-304, 486-499

- Tracks subgraph depth with `_subgraph_depth` context variable
- Detects nested subgraph execution
- Propagates parent run_id and parent_event_id to subgraphs
- Maintains proper parent-child relationships across graph boundaries

**Key Features**:
- Top-level graph: `depth=0`
- Nested subgraph: `depth=1, parent_run_id=parent_graph_run_id`
- Metadata includes `is_subgraph`, `depth`, `parent_run_id`

### 4. ✅ Rich Node Metadata

**Implementation**: Lines 85-194, 362-380, 554-572

**Extracted Metadata**:
- `function_name`: Name of the function executed by the node
- `class_name`: Class name if node is a method
- `module`: Module where the node function is defined
- `file`: Source file path
- `node_type`: Automatically determined type:
  - `"llm"`: LLM/ChatModel nodes
  - `"tool"`: Tool nodes
  - `"subgraph"`: Nested graph nodes
  - `"chain"`: Chain/Runnable sequence nodes
  - `"custom"`: Custom functions
  - `"graph_node"`: LangGraph-specific nodes

**Example Node Event**:
```json
{
  "event_type": "node_execution",
  "node_name": "research_node",
  "run_id": "uuid...",
  "parent_event_id": "graph_start_uuid...",
  "duration_ms": 234.5,
  "status": "completed",
  "metadata": {
    "function_name": "research_node",
    "node_type": "custom",
    "module": "__main__",
    "file": "/path/to/example.py"
  },
  "state_diff": {...}
}
```

### 5. ✅ Complete Error Tracking

**Implementation**: Lines 393-422, 591-620, 428-433, 628-633

**Error Features**:
- Node-level error tracking with full stack traces
- Graph-level error tracking
- Status tracking: `"completed"` or `"error"`
- Error metadata includes:
  - `error.type`: Exception class name
  - `error.message`: Error message
  - `error.traceback`: Full stack trace

**Failed Node Event**:
```python
error_event = NodeExecutionEvent(
    run_id=graph_run_id,
    node_name=node_name,
    data={
        "status": "error",
        "error": {
            "type": "ValueError",
            "message": "Invalid input",
            "traceback": "Traceback (most recent call last)..."
        }
    }
)
```

### 6. ✅ Debug Logging

**Implementation**: Lines 394-397, 424-425, 430-433, 592-595, 622-623, 630-633, 666-667

**Logging Levels**:
- `logger.debug()`: Metadata extraction failures (non-critical)
- `logger.error(..., exc_info=True)`: Node/graph tracking failures (critical)
- Full exception context with stack traces
- Identifies specific failure points (node name, operation type)

**Example Logs**:
```
ERROR Failed to track node 'research_node': ValueError...
ERROR Failed to process chunk: TypeError...
ERROR Graph execution failed: RuntimeError...
ERROR Failed to track agent end: Exception...
```

### 7. ✅ Stream and Invoke Support

**Implementation**: Lines 275-471 (stream), 473-667 (invoke)

- Both `stream()` and `invoke()` methods are fully instrumented
- Invoke internally uses stream for consistency
- Stream yields chunks while tracking in real-time
- No duplicate tracking when invoke calls stream

### 8. ✅ State Diff Tracking

**Implementation**: Lines 197-249 (existing, preserved)

- Calculates state changes between node executions
- Shows what each node modified in the state
- Supports dataclasses, dicts, and custom objects
- Includes before/after values for each changed field

## Usage

### Basic Usage (Automatic)

```python
from gati import observe

# Initialize GATI - that's all you need!
observe.init(backend_url="http://localhost:8000")

# Use LangGraph normally
from langgraph.graph import StateGraph

graph = StateGraph(MyState)
graph.add_node("node1", node1_func)
graph.add_node("node2", node2_func)
app = graph.compile()  # Automatically instrumented!

# Everything is tracked automatically
result = app.invoke({"input": "..."})
```

### LLM Tracking (Automatic)

```python
from langchain_openai import ChatOpenAI

def llm_node(state):
    llm = ChatOpenAI(model="gpt-3.5-turbo")
    # This LLM call is automatically tracked!
    response = llm.invoke("What is 2+2?")
    return {"result": response.content}

# Add node to graph - LLM tracking is automatic
graph.add_node("llm_node", llm_node)
```

### Nested Subgraph (Automatic)

```python
# Create subgraph
subgraph = create_subgraph().compile()

def parent_node(state):
    # Subgraph invocation is automatically tracked as nested
    return subgraph.invoke(state)

# Add to parent graph
parent_graph.add_node("parent", parent_node)
```

## Testing

**Test File**: [`examples/langgraph_advanced_example.py`](examples/langgraph_advanced_example.py)

Run the test:
```bash
cd examples
python langgraph_advanced_example.py
```

**Test Coverage**:
1. Multi-node graphs with sequential execution
2. LLM calls within nodes (if API key configured)
3. Nested subgraph execution
4. Stream vs invoke methods
5. Error handling (commented out, can be enabled)

## Event Tracking Summary

| Event Type | When Tracked | Parent Relationship | Metadata Included |
|------------|--------------|---------------------|-------------------|
| `AgentStartEvent` | Graph execution starts | Top-level or nested parent | graph_type, method, depth, is_subgraph |
| `NodeExecutionEvent` | Each node executes | Graph start event | function_name, node_type, duration, status, state_diff |
| `LLMCallEvent` | LLM call in node | Node event | model, tokens, cost, latency (via LangChain callback) |
| `ToolCallEvent` | Tool call in node | Node event | tool_name, input/output (via LangChain callback) |
| `AgentEndEvent` | Graph execution ends | Graph start event | total_duration, status, error |

## Architecture Improvements

### Context Management
- Uses `contextvars` for thread-safe context tracking
- Supports nested execution contexts
- Proper token-based context cleanup

### Parent-Child Relationships
```python
# Graph level
with run_context(parent_id=parent_run_id) as graph_run_id:
    # Set graph start as parent for all events
    set_parent_event_id(agent_start_event_id)

    # Node level
    node_event.parent_event_id = agent_start_event_id
    observe.track_event(node_event)

    # Set node as parent for nested calls
    set_parent_event_id(node_event.event_id)
```

### LangChain Integration
```python
# LangChain callbacks automatically use context
gati_callbacks = observe.get_callbacks()  # Returns GatiLangChainCallback
config["callbacks"] = gati_callbacks

# Callback handler reads context
run_id = get_current_run_id()  # Gets graph_run_id
parent_event_id = get_parent_event_id()  # Gets node_event_id

# Creates LLM event with proper hierarchy
llm_event = LLMCallEvent(
    run_id=run_id,
    parent_event_id=parent_event_id,
    ...
)
```

## Benefits

1. **Zero Code Changes**: Just call `observe.init()` - everything else is automatic
2. **Complete Visibility**: Tracks graphs, nodes, LLMs, tools, and subgraphs
3. **Proper Hierarchy**: Full parent-child relationships for distributed tracing
4. **Rich Context**: Function names, types, durations, errors, state diffs
5. **Production Ready**: Comprehensive error handling and debug logging
6. **Performance Aware**: Minimal overhead, efficient serialization

## Backward Compatibility

✅ All existing functionality is preserved:
- Node-level state diff tracking (unchanged)
- `_in_graph_execution` flag logic (unchanged)
- Existing event structures (enhanced, not replaced)
- Original methods are properly wrapped and restored

## Future Enhancements

Potential improvements (not included in current implementation):
1. Async graph support (astream, ainvoke)
2. Graph visualization generation
3. Performance profiling and bottleneck detection
4. Custom metadata injection API
5. Conditional tracking based on predicates

## Files Modified

1. [`sdk/gati/instrumentation/langgraph/auto_inject.py`](sdk/gati/instrumentation/langgraph/auto_inject.py) - Enhanced implementation
2. [`examples/langgraph_advanced_example.py`](examples/langgraph_advanced_example.py) - New comprehensive test

## Conclusion

The LangGraph automatic instrumentation is now feature-complete and production-ready. It provides comprehensive observability for LangGraph applications with zero code changes required from users. All requirements have been implemented:

✅ Track all LLM calls and tools inside nodes
✅ Propagate run_id and parent_event_id throughout execution
✅ Support nested graphs/subgraphs
✅ Add rich node metadata
✅ Track streaming fully
✅ Add debug logging for failures
✅ Preserve existing functionality

The implementation integrates seamlessly with LangChain instrumentation and provides a complete observability solution for LangGraph-based applications.
