# GATI SDK

GATI SDK is a Python library for tracking AI agent executions, including LLM calls, tool usage, and state changes. It sends events to a local backend for monitoring and analysis.

## Features

- **Event Tracking**: Track LLM calls, tool usage, agent lifecycle, and node executions
- **Local Backend**: Send events to a local backend for analysis
- **Agent Instrumentation**: Automatic instrumentation for popular AI frameworks (LangChain, LangGraph)
- **Telemetry**: Real-time event reporting and monitoring

## Installation

```bash
pip install -e .
```

Or install from source:

```bash
git clone <repository-url>
cd gati-sdk/sdk
pip install -e .
```

## Requirements

- Python >= 3.9
- Dependencies: `requests`, `typing-extensions`

## Usage

The SDK provides decorators and instrumentation utilities to track your AI agent executions. See the examples directory for usage patterns.

## Automatic Framework Integration

GATI automatically instruments popular AI frameworks with **zero code changes**. Just call `observe.init()` and all operations are tracked automatically.

**Supported Frameworks:**
- **LangChain** (0.2+, 1.0+) - Automatic tracking of LLMs, chains, agents, tools
- **LangGraph** (1.0+) - Automatic tracking of graphs, nodes, state transitions

## LangChain Integration

GATI automatically tracks all LangChain operations with **zero code changes** to your existing LangChain code.

### Quick Start (2 lines)

```python
from gati import observe

# Just initialize - that's it! All LangChain calls are auto-tracked
observe.init(backend_url="http://localhost:8000", agent_name="my_agent")

# Use LangChain normally - no changes needed
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-3.5-turbo")
response = llm.invoke("What's 2+2?")  # ← Automatically tracked!
```

### How It Works

When you call `observe.init()`, GATI:
1. Enables automatic callback injection into all LangChain Runnables
2. Every LLM call, chain execution, and tool invocation is automatically tracked
3. No need to pass `callbacks=...` parameter anywhere
4. Works with all LangChain versions (0.2+, 1.0+)

### Automatic Tracking With Agents

```python
from gati import observe
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import tool

observe.init(backend_url="http://localhost:8000")

@tool
def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b

# Create LLM and agent normally - no callbacks parameter needed!
llm = ChatOpenAI(model="gpt-3.5-turbo")
agent = create_tool_calling_agent(llm, [multiply], prompt)
executor = AgentExecutor(agent=agent, tools=[multiply])

result = executor.invoke({"input": "What is 5 * 3?"})
# Automatically tracks: LLM calls, tool invocations, agent flow
```

### Manual Mode (Optional)

If you prefer explicit callbacks or need to disable auto-injection:

```python
from gati import observe

# Disable auto-injection
observe.init(backend_url="http://localhost:8000", auto_inject=False)

# Manually pass callbacks
llm = ChatOpenAI(model="gpt-3.5-turbo", callbacks=observe.get_callbacks())
```

### What Gets Tracked

- **All LLM calls**: prompt, response, tokens, latency, cost
- **Chain executions**: inputs, outputs, duration
- **Tool usage**: name, input, output, latency
- **Agent reasoning steps**
- **Retriever queries**

### Custom Tools

LangChain built-in tools are auto-tracked. For custom tools with external API calls, add `@track_tool`:

```python
from gati import track_tool

@track_tool
def my_api_call(query: str):
    return requests.get(f"api.com?q={query}")
```

### Run the example

```bash
cd examples/langchain_example
pip install -r requirements.txt
python main.py
```

### Troubleshooting

- **No events showing up**: Ensure `observe.init(...)` is called before `observe.auto_instrument()` and before any LangChain objects are created.
- **Double events**: Calling `observe.auto_instrument()` multiple times is safe; the SDK prevents duplicate handler registration. If you still see duplicates, check for multiple processes or custom callback handlers.
- **Missing LangChain**: Auto-instrumentation only activates when LangChain is installed and importable. Install it in your environment and restart the process.
- **Network errors**: By default, events are sent asynchronously. Verify `backend_url` and that the backend is reachable. You can also call `observe.flush()` to force-send buffered events before shutdown.

## LangGraph Integration

GATI automatically tracks all LangGraph operations with **zero code changes** to your existing LangGraph code.

### Quick Start (2 lines)

```python
from gati import observe

# Just initialize - that's it! All LangGraph graphs are auto-tracked
observe.init(backend_url="http://localhost:8000", agent_name="my_agent")

# Use LangGraph normally - no changes needed
from langgraph.graph import StateGraph, END
from typing import TypedDict

class State(TypedDict):
    message: str
    count: int

def process_node(state: State) -> State:
    return {"message": "processed", "count": state["count"] + 1}

graph = StateGraph(State)
graph.add_node("process", process_node)
graph.set_entry_point("process")
graph.add_edge("process", END)

app = graph.compile()  # ← Automatically wrapped with GATI tracking!
result = app.invoke({"message": "hello", "count": 0})  # ← Automatically tracked!
```

### How It Works

When you call `observe.init()`, GATI:
1. Automatically monkeypatches `StateGraph.compile()` to wrap all graphs
2. Every node execution, state transition, and graph invocation is tracked
3. No need to manually wrap graphs with `GatiStateGraphWrapper`
4. Works with all LangGraph 1.0+ features

### Automatic Tracking Features

```python
from gati import observe
from langgraph.graph import StateGraph, END

observe.init(backend_url="http://localhost:8000")

# Define your graph as usual
graph = StateGraph(State)
graph.add_node("node1", node1_func)
graph.add_node("node2", node2_func)
graph.add_conditional_edges("node1", router_func)
graph.set_entry_point("node1")

# Compile normally - GATI wraps it automatically!
app = graph.compile()

# All methods are tracked automatically:
result = app.invoke({"input": "test"})        # ← Tracked
for chunk in app.stream({"input": "test"}):   # ← Tracked
    print(chunk)

# Async methods too:
result = await app.ainvoke({"input": "test"}) # ← Tracked
async for chunk in app.astream({"input": "test"}):  # ← Tracked
    print(chunk)
```

### What Gets Tracked

- **Graph-level execution**: invoke, stream, ainvoke, astream
- **Node executions**: every node run with timing and status
- **State transitions**: state before/after each node with diff calculation
- **State diffs**: only changed fields are captured (efficient)
- **Errors**: node failures with error details (without suppressing errors)
- **Async operations**: full support for async nodes and methods

### State Diff Example

LangGraph state changes are automatically calculated:

```python
# Initial state: {"count": 0, "message": ""}
# After node: {"count": 1, "message": "processed"}

# GATI captures the diff:
{
  "count": {"before": 0, "after": 1},
  "message": {"before": "", "after": "processed"}
}
```

### Manual Mode (Optional)

If you prefer explicit wrapping or need to disable auto-instrumentation:

```python
from gati import observe
from gati.instrumentation.langgraph import GatiStateGraphWrapper

# Disable auto-instrumentation
observe.init(backend_url="http://localhost:8000", auto_inject=False)

# Manually wrap graphs
graph = StateGraph(State)
# ... add nodes ...
wrapped = GatiStateGraphWrapper(graph)
app = wrapped.compile()
```

### Run the example

```bash
cd examples
pip install langgraph
python langgraph_example.py
```

### Troubleshooting

- **No events showing up**: Ensure `observe.init(...)` is called before creating or compiling any StateGraph instances.
- **Missing LangGraph**: Auto-instrumentation only activates when LangGraph is installed. Install with: `pip install langgraph`
- **State serialization errors**: GATI safely serializes all state types (TypedDict, dict, dataclass). If you see warnings, check for non-serializable objects in your state.
- **Network errors**: Events are sent asynchronously. Verify `backend_url` and call `observe.flush()` before shutdown to ensure all events are sent.

## Project Structure

```
gati/
├── core/           # Core event system and client
├── decorators/     # Decorators for tracking
├── instrumentation/# Framework-specific instrumentation
├── telemetry/      # Event reporting
└── utils/          # Utility functions
```

## License

See LICENSE file for details.

