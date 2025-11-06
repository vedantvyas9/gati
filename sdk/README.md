# GATI SDK - Technical Deep Dive

**A comprehensive guide to understanding the GATI SDK's architecture, instrumentation mechanisms, and data flow.**

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core System Components](#core-system-components)
3. [Instrumentation Deep Dive](#instrumentation-deep-dive)
   - [LangChain Instrumentation](#langchain-instrumentation)
   - [LangGraph Instrumentation](#langgraph-instrumentation)
   - [Custom Python Instrumentation](#custom-python-instrumentation)
4. [Event System & Data Flow](#event-system--data-flow)
5. [Context Management & Run Tracking](#context-management--run-tracking)
6. [Buffering & Network Communication](#buffering--network-communication)
7. [Class Structure Reference](#class-structure-reference)

---

## Architecture Overview

The GATI SDK is designed around **event-driven observability** for AI agent workflows. Think of it as a surveillance system that watches your agent execute, captures every important action (LLM calls, tool uses, state changes), packages them into structured events, and ships them to a backend for analysis.

### High-Level Flow

```
┌─────────────────┐
│  User's Agent   │
│   (LangChain,   │
│   LangGraph,    │
│   or Custom)    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│  Instrumentation Layer      │
│  (Intercepts execution)     │
│  - Callbacks (LangChain)    │
│  - Wrappers (LangGraph)     │
│  - Decorators (Custom)      │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  Event Creation             │
│  (Structured data objects)  │
│  - AgentStartEvent          │
│  - LLMCallEvent             │
│  - ToolCallEvent            │
│  - NodeExecutionEvent       │
│  - AgentEndEvent            │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  Context Manager            │
│  (Thread-local run tracking)│
│  - Assigns run_id           │
│  - Manages parent-child     │
│  - Sets event hierarchy     │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  Event Buffer               │
│  (Thread-safe batching)     │
│  - Collects events          │
│  - Batches by size/time     │
│  - Background flush thread  │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  HTTP Client                │
│  (Async network sender)     │
│  - Retry logic              │
│  - Connection pooling       │
│  - Error handling           │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  Backend API                │
│  (Storage & Analysis)       │
└─────────────────────────────┘
```

---

## Core System Components

### 1. **Observe Class** (Singleton Pattern)

**File:** `gati/observe.py`

The `Observe` class is the **single entry point** for all SDK functionality. It's implemented as a singleton, meaning only one instance exists across your entire application.

**Why Singleton?**
- Ensures consistent state across all modules
- Prevents duplicate instrumentation
- Centralizes configuration management

**Key Responsibilities:**
1. **Initialization** - Sets up the entire SDK pipeline
2. **Configuration Management** - Stores backend URL, API keys, batch settings
3. **Component Orchestration** - Creates and wires together Buffer, Client, Context
4. **Event Tracking** - Central method for recording events
5. **Lifecycle Management** - Startup and shutdown coordination

**Class Structure:**
```python
class Observe:
    _instance: Optional['Observe'] = None  # Singleton instance
    _lock = threading.Lock()               # Thread-safety for singleton
    _initialized: bool = False             # Init guard

    # Core components
    _config: Optional[Config]              # Configuration object
    _buffer: Optional[EventBuffer]         # Event batching buffer
    _client: Optional[EventClient]         # HTTP client
    _detector: Optional[FrameworkDetector] # Auto-detect frameworks

    # Instrumentation tracking
    _instrumented_frameworks: Dict[str, bool]
    _instrumentation_status: Dict[str, Any]
```

**Initialization Flow:**
```python
observe.init(backend_url="http://localhost:8000")
```

What happens internally:
1. Creates `Config` object with settings
2. Instantiates `EventClient` (HTTP connection pool)
3. Creates `EventBuffer` with flush callback = `client.send_events`
4. Starts buffer's background flush thread
5. Enables auto-injection for LangChain (if requested)
6. Instruments LangGraph (if available)

### 2. **Event System**

**File:** `gati/core/event.py`

Events are **immutable data objects** (dataclasses) representing discrete occurrences in your agent's execution.

**Base Event Class:**
```python
@dataclass
class Event:
    event_type: str                # Discriminator (llm_call, tool_call, etc.)
    run_id: str                    # Unique execution ID
    timestamp: str                 # ISO 8601 timestamp
    agent_name: str                # Name of the agent
    event_id: str                  # Unique event ID (UUID)
    parent_event_id: Optional[str] # For building event trees
    data: Dict[str, Any]           # Type-specific payload
```

**Event Types:**

| Event Type | Purpose | Key Fields |
|------------|---------|------------|
| `AgentStartEvent` | Marks agent execution start | `input`, `metadata` |
| `AgentEndEvent` | Marks agent execution end | `output`, `total_duration_ms`, `total_cost` |
| `LLMCallEvent` | Tracks LLM API calls | `model`, `prompt`, `completion`, `tokens_in`, `tokens_out`, `latency_ms`, `cost` |
| `ToolCallEvent` | Tracks tool/function executions | `tool_name`, `input`, `output`, `latency_ms` |
| `NodeExecutionEvent` | Tracks graph node execution | `node_name`, `state_before`, `state_after`, `duration_ms` |
| `StepEvent` | Generic step/chain execution | `step_name`, `input`, `output`, `duration_ms` |

**Event Lifecycle:**
1. **Creation:** Instantiated by instrumentation code
2. **Enrichment:** Automatically gets `timestamp` and `event_id` in `__post_init__`
3. **Context Injection:** `run_id` and `parent_event_id` set from thread-local context
4. **Serialization:** Converted to dict via `to_dict()`, then to JSON via `to_json()`
5. **Buffering:** Added to `EventBuffer`
6. **Batching:** Grouped with other events
7. **Transmission:** Sent to backend in batch

### 3. **Context Manager**

**File:** `gati/core/context.py`

The context manager solves a critical problem: **How do we connect related events across async execution and nested function calls?**

**Solution: Thread-Local Storage + Context Stack**

**Core Concept:**
- Each thread maintains its own **stack of RunContext objects**
- Each `RunContext` represents one level of execution (agent → chain → LLM call)
- When you enter a new context (e.g., start an agent), push onto stack
- When you exit, pop from stack
- Current run_id is always the top of the stack

**RunContext Object:**
```python
class RunContext:
    run_id: str                    # Unique ID for this execution
    parent_id: Optional[str]       # Parent run's ID (for nesting)
    parent_event_id: Optional[str] # Parent event's ID (for event tree)
    depth: int                     # How deep in the stack (0 = root)
```

**RunContextManager (Singleton):**
```python
class RunContextManager:
    _local = threading.local()  # Thread-local storage

    @classmethod
    def _get_stack(cls) -> List[RunContext]:
        """Get or create stack for current thread"""
        if not hasattr(cls._local, 'stack'):
            cls._local.stack = []
        return cls._local.stack
```

**Usage Pattern:**
```python
# Start a new run context
with run_context() as run_id:
    # All events created here get this run_id automatically
    observe.track_event(LLMCallEvent(...))  # run_id is auto-injected

    # You can nest contexts
    with run_context() as child_run_id:
        # This has parent_id = run_id
        observe.track_event(ToolCallEvent(...))
```

**How It Works:**
1. `run_context()` generates a new UUID for `run_id`
2. Checks current stack - if not empty, sets `parent_id` to current run_id
3. Creates `RunContext` object, pushes to stack
4. Yields `run_id` to user code
5. When context exits (via `with` statement), pops from stack
6. Any code calling `get_current_run_id()` gets the top of the stack

**Parent-Child Event Relationships:**

Beyond run IDs, we also track event-level parent-child relationships:

```python
# Set a parent event ID in context
set_parent_event_id(start_event.event_id)

# All subsequent events created get this as their parent
event = LLMCallEvent(...)  # Automatically sets parent_event_id
```

This creates an **event tree** that shows execution flow:
```
AgentStartEvent (id: abc123)
├── LLMCallEvent (parent: abc123)
├── ToolCallEvent (parent: abc123)
│   └── LLMCallEvent (parent: tool_event_id)
└── AgentEndEvent (parent: abc123)
```

### 4. **Event Buffer**

**File:** `gati/core/buffer.py`

The buffer is a **thread-safe queue** that batches events before sending them to reduce network overhead.

**Design Pattern: Producer-Consumer**

**Key Components:**
```python
class EventBuffer:
    _events: List[Event]              # The buffer (protected by lock)
    _lock: threading.Lock()           # Ensures thread-safety
    flush_callback: Callable          # Function to call when flushing
    batch_size: int                   # Max events before auto-flush
    flush_interval: float             # Max seconds between flushes

    _thread: Optional[threading.Thread]  # Background flush worker
    _stop_event: threading.Event()       # Signal to stop worker
    _running: bool                       # Worker state flag
```

**Batching Strategy:**

Events are flushed when **either** condition is met:
1. **Size-based:** Buffer contains >= `batch_size` events (default: 10)
2. **Time-based:** `flush_interval` seconds have elapsed (default: 1.0s)

**Thread Safety:**

The buffer uses a **mutex lock** to prevent race conditions:

```python
def add_event(self, event: Event):
    with self._lock:  # Acquire lock
        self._events.append(event)

        if len(self._events) >= self.batch_size:
            self._flush_locked()  # Flush while holding lock
    # Lock automatically released
```

**Background Flush Worker:**

A daemon thread runs continuously, checking if it's time to flush:

```python
def _flush_worker(self):
    while not self._stop_event.is_set():
        # Sleep for flush_interval (or until stop signal)
        self._stop_event.wait(timeout=self.flush_interval)

        with self._lock:
            time_since_flush = time.time() - self._last_flush_time
            if time_since_flush >= self.flush_interval and self._events:
                self._flush_locked()
```

**Flush Process:**

```python
def _flush_locked(self):
    if not self._events:
        return

    # 1. Copy events (so we can release lock quickly)
    events_to_send = self._events.copy()

    # 2. Clear buffer
    self._events.clear()
    self._last_flush_time = time.time()

    # 3. Send events (outside lock to avoid blocking)
    try:
        self.flush_callback(events_to_send)
    except Exception as e:
        # Log but don't crash - events are already removed from buffer
        print(f"Error in flush callback: {e}")
```

**Why This Design?**

- **Performance:** Batching reduces HTTP requests (10 events → 1 request instead of 10)
- **Non-blocking:** Background thread means user code never waits
- **Reliability:** Lock ensures no events are lost to race conditions
- **Graceful shutdown:** `stop()` method flushes remaining events before exit

### 5. **HTTP Client**

**File:** `gati/core/client.py`

The client handles **network communication** with the backend API.

**Design Pattern: Connection Pooling + Retry Logic**

**Class Structure:**
```python
class EventClient:
    backend_url: str                # Backend server base URL
    api_key: Optional[str]          # Authentication token
    timeout: float                  # Request timeout (default: 10s)
    max_retries: int                # Max retry attempts (default: 3)

    events_url: str                 # Computed: backend_url + "/api/events"
    _session: requests.Session      # Connection pool
```

**Connection Pooling:**

Uses `requests.Session` for connection reuse:
- Maintains a pool of TCP connections
- Reuses connections across requests (faster than creating new ones)
- Automatically handles keep-alive

**Request Flow:**

```python
def send_events(self, events: List[Event]):
    # 1. Convert events to dicts
    events_dict = [e.to_dict() for e in events]

    # 2. Send in background thread (non-blocking)
    thread = threading.Thread(
        target=self._send_events_sync,
        args=(events_dict,),
        daemon=True
    )
    thread.start()
```

**Retry Strategy: Exponential Backoff**

```python
def _send_with_retry(self, events):
    for attempt in range(self.max_retries + 1):
        try:
            response = self._session.post(
                self.events_url,
                json={"events": events},
                timeout=self.timeout
            )

            # Success codes
            if response.status_code in (200, 201, 204):
                return True

            # Client errors (4xx) - don't retry (except 429 rate limit)
            if 400 <= response.status_code < 500 and response.status_code != 429:
                print(f"Client error: {response.status_code}")
                return False

            # Server errors (5xx) or rate limit - retry with backoff
            if attempt < self.max_retries:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                time.sleep(wait_time)

        except requests.exceptions.Timeout:
            # Retry on timeout
            if attempt < self.max_retries:
                wait_time = 2 ** attempt
                time.sleep(wait_time)

        except requests.exceptions.ConnectionError:
            # Retry on connection error
            if attempt < self.max_retries:
                wait_time = 2 ** attempt
                time.sleep(wait_time)

    return False
```

**Why Exponential Backoff?**
- Prevents overwhelming a struggling server
- Gives server time to recover
- Avoids creating a "retry storm"

**Request Format:**

```json
POST /api/events
{
  "events": [
    {
      "event_type": "llm_call",
      "run_id": "abc-123",
      "timestamp": "2024-01-15T10:30:00.000Z",
      "agent_name": "research_agent",
      "event_id": "def-456",
      "parent_event_id": null,
      "data": {
        "model": "gpt-4",
        "prompt": "What is quantum computing?",
        "completion": "Quantum computing is...",
        "tokens_in": 10,
        "tokens_out": 50,
        "latency_ms": 1234.5,
        "cost": 0.002
      }
    }
  ]
}
```

---

## Instrumentation Deep Dive

Now we get to the **core magic** - how does GATI actually capture data from different frameworks?

### LangChain Instrumentation

**File:** `gati/instrumentation/langchain.py`

LangChain provides a **callback system** - a hooks mechanism that lets you inject custom code at various execution points. GATI uses this to observe what's happening.

#### Approach 1: Auto-Injection via Monkeypatching

**Goal:** Make instrumentation completely automatic - user just calls `observe.init()` and all LangChain code is tracked.

**How It Works:**

1. **Patch the Runnable base class**

All LangChain components (LLMs, Chains, Agents) inherit from `Runnable`, which has three key methods:
- `invoke()` - synchronous execution
- `batch()` - batch execution
- `stream()` - streaming execution

We **replace these methods** with our own wrapped versions:

```python
def enable_auto_injection():
    # Store original methods
    original_invoke = Runnable.invoke
    original_batch = Runnable.batch
    original_stream = Runnable.stream

    # Create wrapped versions
    def patched_invoke(self, input, config=None, **kwargs):
        return _invoke_with_callbacks(original_invoke, self, input, config, **kwargs)

    # Replace methods on the Runnable class
    Runnable.invoke = patched_invoke
    Runnable.batch = patched_batch
    Runnable.stream = patched_stream
```

2. **Inject callbacks at invocation time**

Inside `_invoke_with_callbacks`:

```python
def _invoke_with_callbacks(original_method, runnable_self, input_data, config, **kwargs):
    # Check if observe is initialized
    if not observe._initialized:
        return original_method(runnable_self, input_data, config, **kwargs)

    # Handle config
    if config is None:
        config = {}

    # Check if user already set callbacks (respect user choice)
    if config.get("callbacks"):
        return original_method(runnable_self, input_data, config, **kwargs)

    # Determine if this is an agent or just an LLM
    is_agent = _is_agent_runnable(runnable_self)

    # Get current run context
    existing_run_id = get_current_run_id()

    if existing_run_id:
        # Already in a run context - just inject callbacks
        config["callbacks"] = observe.get_callbacks()
        return original_method(runnable_self, input_data, config, **kwargs)

    if not is_agent:
        # Simple LLM call - inject callbacks but don't create run context
        config["callbacks"] = observe.get_callbacks()
        return original_method(runnable_self, input_data, config, **kwargs)

    # This is a top-level agent - create run context
    with run_context() as new_run_id:
        # Create agent start event
        start_event = AgentStartEvent(
            run_id=new_run_id,
            agent_name=_extract_agent_name(runnable_self),
            input=serialize(input_data),
            metadata={"auto_tracked": True}
        )

        # Set as parent for all child events
        set_parent_event_id(start_event.event_id)
        observe.track_event(start_event)

        # Inject callbacks
        config["callbacks"] = observe.get_callbacks()

        # Execute
        try:
            output = original_method(runnable_self, input_data, config, **kwargs)
            return output
        finally:
            # Create agent end event
            end_event = AgentEndEvent(
                run_id=new_run_id,
                output=serialize(output),
                total_duration_ms=duration_ms
            )
            observe.track_event(end_event)
```

**Agent Detection:**

How do we know if something is an "agent" vs a simple LLM?

```python
def _is_agent_runnable(runnable):
    class_name = type(runnable).__name__.lower()
    module_name = type(runnable).__module__.lower()

    # Check for agent indicators
    agent_indicators = ["agent", "executor", "graph", "pregel"]
    llm_indicators = ["chatmodel", "llm", "openai", "anthropic"]

    # If it's an LLM, not an agent
    if any(indicator in class_name for indicator in llm_indicators):
        return False

    # If it matches agent patterns, it's an agent
    if any(indicator in class_name for indicator in agent_indicators):
        return True

    # Default: treat as non-agent (safer)
    return False
```

This prevents us from creating run contexts for every LLM call (which would be overwhelming).

#### Approach 2: GatiLangChainCallback

**The callback handler** is where the actual event tracking happens.

```python
class GatiLangChainCallback(BaseCallbackHandler):
    def __init__(self):
        super().__init__()

        # Timing stores (keyed by LangChain's internal run_id)
        self._llm_start_times: Dict[str, float] = {}
        self._tool_start_times: Dict[str, float] = {}

        # Name caches
        self._tool_names: Dict[str, str] = {}

        # Run ID mappings (LangChain run_id → GATI run_id)
        self._run_id_mapping: Dict[str, str] = {}

        # Event ID mappings (for parent relationships)
        self._event_id_mapping: Dict[str, str] = {}
```

**LLM Call Tracking:**

```python
def on_llm_start(self, serialized, prompts, **kwargs):
    """Called when LLM starts"""
    # Get LangChain's internal run_id
    lc_run_id = kwargs.get("run_id")
    lc_parent_run_id = kwargs.get("parent_run_id")

    # Get GATI run_id from context (or create mapping)
    gati_run_id = get_current_run_id()
    if not gati_run_id:
        # Check if parent has a mapping
        if lc_parent_run_id in self._run_id_mapping:
            gati_run_id = self._run_id_mapping[lc_parent_run_id]
        else:
            # Create new GATI run_id for this LangChain execution
            gati_run_id = generate_run_id()
            self._run_id_mapping[lc_run_id] = gati_run_id

    # Store timing
    self._llm_start_times[lc_run_id] = time.monotonic()

    # Get parent event ID from context or mapping
    parent_event_id = get_parent_event_id()
    if not parent_event_id and lc_parent_run_id:
        parent_event_id = self._event_id_mapping.get(lc_parent_run_id)

    # Extract model and prompts
    model_name = self._extract_model_name(serialized)
    system_prompt, user_prompt = self._extract_system_and_user_prompts(prompts)

    # Create event
    event = LLMCallEvent(
        run_id=gati_run_id,
        model=model_name,
        prompt=user_prompt,
        system_prompt=system_prompt,
        data={"status": "started"}
    )

    # Set parent if available
    if parent_event_id:
        event.parent_event_id = parent_event_id

    # Store event_id mapping for this LangChain run
    self._event_id_mapping[lc_run_id] = event.event_id

    # Track event
    observe.track_event(event)

def on_llm_end(self, response, **kwargs):
    """Called when LLM completes"""
    lc_run_id = kwargs.get("run_id")

    # Get GATI run_id from mapping
    gati_run_id = self._run_id_mapping.get(lc_run_id, "")

    # Calculate latency
    start_time = self._llm_start_times.get(lc_run_id, 0)
    latency_ms = (time.monotonic() - start_time) * 1000.0

    # Extract response data
    model_name = self._extract_model_from_response(response)
    completion = self._extract_completion_text(response)
    tokens_in, tokens_out = self._extract_token_usage(response)
    cost = calculate_cost(model_name, tokens_in, tokens_out)

    # Create event
    event = LLMCallEvent(
        run_id=gati_run_id,
        model=model_name,
        completion=completion,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=latency_ms,
        cost=cost,
        data={"status": "completed"}
    )

    # Track event
    observe.track_event(event)

    # Cleanup
    self._llm_start_times.pop(lc_run_id, None)
```

**Tool Call Tracking:**

Similar pattern for tools:

```python
def on_tool_start(self, tool, input_str, **kwargs):
    """Called when tool starts"""
    lc_run_id = kwargs.get("run_id")
    gati_run_id = get_current_run_id() or self._run_id_mapping.get(lc_run_id, "")

    # Store timing
    self._tool_start_times[lc_run_id] = time.monotonic()
    self._tool_names[lc_run_id] = self._extract_tool_name(tool)

    # Create event
    event = ToolCallEvent(
        run_id=gati_run_id,
        tool_name=self._tool_names[lc_run_id],
        input={"input_str": input_str},
        data={"status": "started"}
    )

    observe.track_event(event)

def on_tool_end(self, output, **kwargs):
    """Called when tool completes"""
    lc_run_id = kwargs.get("run_id")
    gati_run_id = self._run_id_mapping.get(lc_run_id, "")

    # Calculate latency
    latency_ms = (time.monotonic() - self._tool_start_times[lc_run_id]) * 1000.0

    # Create event
    event = ToolCallEvent(
        run_id=gati_run_id,
        tool_name=self._tool_names[lc_run_id],
        output={"output": output},
        latency_ms=latency_ms,
        data={"status": "completed"}
    )

    observe.track_event(event)

    # Cleanup
    self._tool_start_times.pop(lc_run_id, None)
    self._tool_names.pop(lc_run_id, None)
```

**Prompt Parsing:**

LangChain prompts can be strings or complex message objects. We parse them:

```python
def _extract_system_and_user_prompts(prompts):
    """Extract system and user prompts from LangChain prompts"""
    system_parts = []
    user_parts = []

    for prompt in prompts:
        # Case 1: String prompt
        if isinstance(prompt, str):
            user_parts.append(prompt)
            continue

        # Case 2: Message list (ChatML format)
        messages = getattr(prompt, "messages", None)
        if messages:
            for msg in messages:
                # Get message type
                msg_type = getattr(msg, "type", None)
                msg_content = getattr(msg, "content", None)

                # Categorize by type
                if msg_type == "system":
                    system_parts.append(msg_content)
                elif msg_type in ("human", "user", "ai", "assistant"):
                    user_parts.append(msg_content)

    system_prompt = "\n\n".join(system_parts)
    user_prompt = "\n\n".join(user_parts)

    return system_prompt, user_prompt
```

**Data Extracted:**

From LangChain callbacks, we capture:
- **Model name** - from serialized metadata or response
- **Prompts** - separated into system and user prompts
- **Completions** - from response.generations
- **Token usage** - from response.llm_output or generation_info
- **Latency** - via start/end time tracking
- **Cost** - calculated using model name + token counts
- **Tool names** - from tool object
- **Tool inputs/outputs** - serialized to JSON-safe format

### LangGraph Instrumentation

**File:** `gati/instrumentation/langgraph.py`

LangGraph uses **graphs** (state machines) instead of linear chains. We need to track:
1. **Graph-level execution** (invoke, stream)
2. **Individual node execution**
3. **State changes** between nodes

#### Approach: Wrapper Pattern

**Why Not Callbacks?**

LangGraph doesn't have a robust callback system like LangChain. Instead, we **wrap** the graph components.

**Two Levels of Wrapping:**

1. **Node-level wrapping** - Track individual node execution
2. **Pregel-level wrapping** - Track overall graph execution

**Node Wrapping:**

```python
class GatiStateGraphWrapper:
    def __init__(self, graph):
        self.graph = graph
        self.wrapped_nodes = {}
        self._original_nodes = {}

    def _wrap_node(self, node_name, node_func):
        """Wrap a node function to track execution"""

        # Check if async
        is_async = asyncio.iscoroutinefunction(node_func)

        if is_async:
            async def async_wrapper(state, *args, **kwargs):
                start_time = time.monotonic()
                state_before = state
                error = None
                state_after = None

                try:
                    # Execute node
                    result = await node_func(state, *args, **kwargs)
                    state_after = result if result is not None else state
                    return result

                except Exception as e:
                    error = e
                    state_after = state
                    raise

                finally:
                    # Track execution
                    duration_ms = (time.monotonic() - start_time) * 1000.0
                    run_id = get_current_run_id() or ""
                    parent_event_id = get_parent_event_id()

                    # Calculate state diff
                    state_diff = _calculate_state_diff(state_before, state_after)

                    # Create event
                    event = NodeExecutionEvent(
                        run_id=run_id,
                        node_name=node_name,
                        state_before=_serialize_state(state_before),
                        state_after=_serialize_state(state_after),
                        duration_ms=duration_ms,
                        data={
                            "state_diff": state_diff,
                            "status": "error" if error else "completed"
                        }
                    )

                    if parent_event_id:
                        event.parent_event_id = parent_event_id

                    observe.track_event(event)

                    # Set this node's event as parent for child ops
                    set_parent_event_id(event.event_id)

            return async_wrapper

        else:
            # Similar sync wrapper
            ...
```

**State Diff Calculation:**

One of LangGraph's key features is state management. We track what changed:

```python
def _calculate_state_diff(state_before, state_after):
    """Calculate difference between states"""
    diff = {}

    # Convert states to dicts
    if dataclasses.is_dataclass(state_before):
        before_dict = dataclasses.asdict(state_before)
    elif isinstance(state_before, dict):
        before_dict = state_before
    else:
        before_dict = vars(state_before)  # Extract attributes

    # Same for state_after
    if dataclasses.is_dataclass(state_after):
        after_dict = dataclasses.asdict(state_after)
    elif isinstance(state_after, dict):
        after_dict = state_after
    else:
        after_dict = vars(state_after)

    # Compare all keys
    all_keys = set(before_dict.keys()) | set(after_dict.keys())

    for key in all_keys:
        before_val = before_dict.get(key)
        after_val = after_dict.get(key)

        if before_val != after_val:
            diff[key] = {
                'before': serialize(before_val),
                'after': serialize(after_val)
            }

    return diff
```

This gives us insights like:
```json
{
  "messages": {
    "before": ["Hello"],
    "after": ["Hello", "I can help with that"]
  },
  "tools_used": {
    "before": [],
    "after": ["search"]
  }
}
```

**Graph Compilation:**

We intercept the `compile()` method:

```python
def compile(self, *args, **kwargs):
    """Compile graph with instrumentation"""

    # Wrap all nodes
    if hasattr(self.graph, 'nodes'):
        for node_name, node_spec in self.graph.nodes.items():
            if callable(node_spec):
                wrapped = self._wrap_node(node_name, node_spec)
                self.graph.nodes[node_name] = wrapped

    # Compile graph (creates Pregel instance)
    compiled_graph = self.graph.compile(*args, **kwargs)

    # Wrap the Pregel instance
    wrapped_pregel = _wrap_pregel(compiled_graph)

    return wrapped_pregel
```

**Pregel Wrapping:**

Pregel is LangGraph's execution engine. We wrap its methods:

```python
def _wrap_pregel(pregel):
    """Wrap Pregel instance to track graph execution"""

    # Store original methods
    original_invoke = pregel.invoke
    original_stream = pregel.stream

    def wrapped_invoke(input, *args, **kwargs):
        """Wrapped invoke"""
        start_time = time.monotonic()
        error = None
        output = None

        # Create run context
        with run_context() as graph_run_id:
            try:
                # Track agent start
                start_event = AgentStartEvent(
                    run_id=graph_run_id,
                    input=_serialize_state(input),
                    metadata={"graph_type": "langgraph", "method": "invoke"}
                )
                observe.track_event(start_event)

                # Set as parent for all node events
                set_parent_event_id(start_event.event_id)

                # Execute graph
                output = original_invoke(input, *args, **kwargs)

                return output

            except Exception as e:
                error = e
                raise

            finally:
                # Track agent end
                duration_ms = (time.monotonic() - start_time) * 1000.0

                end_event = AgentEndEvent(
                    run_id=graph_run_id,
                    output=_serialize_state(output) if output else {},
                    total_duration_ms=duration_ms,
                    data={
                        "status": "error" if error else "completed"
                    }
                )

                observe.track_event(end_event)

    # Replace methods
    pregel.invoke = wrapped_invoke
    pregel.stream = wrapped_stream  # Similar wrapping

    return pregel
```

**Automatic Instrumentation:**

To make it automatic, we monkeypatch `StateGraph.compile`:

```python
def instrument_langgraph():
    """Automatically instrument all StateGraphs"""

    # Store original compile method
    _original_compile = StateGraph.compile

    def instrumented_compile(self, *args, **kwargs):
        """Instrumented compile"""
        # Wrap with GATI tracking
        wrapper = GatiStateGraphWrapper(self)
        return wrapper.compile(*args, **kwargs)

    # Replace compile method
    StateGraph.compile = instrumented_compile

    return True
```

**Data Captured:**

From LangGraph, we track:
- **Graph invocation** - input, output, total duration
- **Node execution** - which nodes ran, in what order
- **State changes** - before/after state for each node
- **State diffs** - what specifically changed
- **Errors** - which node failed and why
- **Async support** - both sync and async graphs

**Event Hierarchy Example:**

```
AgentStartEvent (graph_run_id)
├── NodeExecutionEvent (node: "retrieve")
│   └── ToolCallEvent (tool: "search")  # If node uses a tool
├── NodeExecutionEvent (node: "generate")
│   └── LLMCallEvent (model: "gpt-4")   # If node uses LLM
└── AgentEndEvent (graph_run_id)
```

### Custom Python Instrumentation

**Files:** `gati/decorators/track_agent.py`, `gati/decorators/track_tool.py`, `gati/decorators/track_step.py`

For custom code (not using LangChain/LangGraph), we provide **Python decorators**.

#### @track_agent Decorator

**Purpose:** Track entire agent execution (equivalent to LangChain's AgentExecutor)

**Usage:**
```python
from gati.decorators import track_agent

@track_agent
def my_custom_agent(query: str) -> str:
    # Your agent logic
    result = do_research(query)
    return result

# Or with custom name
@track_agent(name="research_bot")
def my_agent(query: str) -> str:
    ...
```

**How It Works:**

```python
def track_agent(name=None):
    """Decorator for tracking agent runs"""

    def decorator(func):
        # Determine if function is async
        is_async = inspect.iscoroutinefunction(func)

        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await _track_async_agent(func, name, *args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                return _track_sync_agent(func, name, *args, **kwargs)
            return sync_wrapper

    return decorator

def _track_sync_agent(func, agent_name, *args, **kwargs):
    """Track synchronous agent"""

    # Generate run_id
    run_id = generate_run_id()

    # Get agent name
    name = agent_name or func.__name__

    # Serialize input
    input_data = _serialize_args_kwargs(args, kwargs, func)

    # Track start time
    start_time = time.time()
    error = None
    output_data = {}

    # Create AgentStartEvent
    start_event = AgentStartEvent(
        run_id=run_id,
        agent_name=name,
        input=input_data,
        metadata={}
    )
    observe.track_event(start_event)

    # Enter run context
    with run_context(run_id=run_id):
        # Set this event as parent for all child events
        set_parent_event_id(start_event.event_id)

        try:
            # Execute agent
            result = func(*args, **kwargs)
            output_data = _serialize_value(result)
            return result

        except Exception as e:
            error = {"type": type(e).__name__, "message": str(e)}
            raise

        finally:
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Create AgentEndEvent
            end_event = AgentEndEvent(
                run_id=run_id,
                agent_name=name,
                output=output_data,
                total_duration_ms=duration_ms,
                total_cost=0.0  # TODO: Aggregate from child events
            )

            if error:
                end_event.data["error"] = error

            observe.track_event(end_event)
```

**Input Serialization:**

```python
def _serialize_args_kwargs(args, kwargs, func):
    """Serialize function arguments"""

    # Get function signature
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())

    # Build argument map
    result = {}

    # Map positional args to parameter names
    for i, arg in enumerate(args):
        if i < len(params):
            result[params[i]] = _serialize_value(arg)

    # Add keyword args
    for key, value in kwargs.items():
        result[key] = _serialize_value(value)

    return result

def _serialize_value(value):
    """Serialize a single value"""
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    elif isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_serialize_value(v) for v in value]
    else:
        # Complex objects - use string representation
        return str(value)
```

#### @track_tool Decorator

**Purpose:** Track individual tool/function calls (like LangChain tools)

**Usage:**
```python
from gati.decorators import track_tool

@track_tool
def search_web(query: str) -> str:
    # Tool implementation
    results = google_search(query)
    return results

# Or with custom name
@track_tool(name="web_search")
def search(query: str) -> str:
    ...
```

**Implementation:**

```python
def _track_sync_tool(func, tool_name, *args, **kwargs):
    """Track synchronous tool call"""

    # Get run_id from context (set by parent agent)
    run_id = get_current_run_id() or generate_run_id()

    # Get tool name
    name = tool_name or func.__name__

    # Serialize input
    input_data = _serialize_args_kwargs(args, kwargs, func)

    # Track start time
    start_time = time.time()
    error = None
    output_data = {}

    # Create ToolCallEvent (start)
    start_event = ToolCallEvent(
        run_id=run_id,
        tool_name=name,
        input=input_data,
        data={"status": "started"}
    )

    # Set parent from context
    parent_event_id = get_parent_event_id()
    if parent_event_id:
        start_event.parent_event_id = parent_event_id

    observe.track_event(start_event)

    try:
        # Execute tool
        result = func(*args, **kwargs)
        output_data = _serialize_value(result)
        return result

    except Exception as e:
        error = {"type": type(e).__name__, "message": str(e)}
        raise

    finally:
        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000

        # Create ToolCallEvent (end)
        end_event = ToolCallEvent(
            run_id=run_id,
            tool_name=name,
            output=output_data,
            latency_ms=latency_ms,
            data={"status": "error" if error else "completed"}
        )

        if error:
            end_event.data["error"] = error

        if parent_event_id:
            end_event.parent_event_id = parent_event_id

        observe.track_event(end_event)
```

#### @track_step Decorator

**Purpose:** Track arbitrary steps in your agent (like LangChain chains)

**Usage:**
```python
from gati.decorators import track_step

@track_step(name="extract_entities")
def extract_entities(text: str) -> list:
    # Step implementation
    entities = nlp(text).ents
    return entities
```

**Implementation:** Similar to `@track_tool` but creates `StepEvent` instead.

**Data Captured:**

From decorators, we track:
- **Function name** - or custom name provided
- **Input arguments** - serialized to JSON-safe format
- **Output values** - serialized
- **Execution time** - precise timing
- **Errors** - exception type and message
- **Context** - automatically uses run_id from parent

**Decorator Pattern Benefits:**

1. **Non-invasive** - Just add `@track_agent` above function
2. **Flexible** - Works with sync and async functions
3. **Automatic** - No manual event creation needed
4. **Type-safe** - Preserves function signature and return type

---

## Event System & Data Flow

Let's trace a complete execution through the system.

**Example: Custom Agent with Tool Call**

```python
from gati import observe
from gati.decorators import track_agent, track_tool

observe.init(backend_url="http://localhost:8000")

@track_tool
def calculator(expression: str) -> float:
    return eval(expression)

@track_agent
def math_agent(question: str) -> str:
    # Extract expression
    expression = extract_expression(question)

    # Call tool
    result = calculator(expression)

    return f"The answer is {result}"

# Execute
answer = math_agent("What is 5 + 3?")
```

**Step-by-Step Flow:**

1. **Agent Execution Starts**
   - `@track_agent` decorator intercepts call
   - Generates `run_id` = "abc-123"
   - Creates `AgentStartEvent`:
     ```python
     {
       "event_type": "agent_start",
       "run_id": "abc-123",
       "timestamp": "2024-01-15T10:30:00.000Z",
       "event_id": "event-001",
       "agent_name": "math_agent",
       "data": {
         "input": {"question": "What is 5 + 3?"}
       }
     }
     ```
   - Calls `observe.track_event(start_event)`

2. **Event Buffering (AgentStartEvent)**
   - Event enters `EventBuffer`
   - `buffer.add_event(start_event)` acquires lock
   - Appends to `_events` list
   - Checks batch size (currently 1 < 10)
   - Releases lock
   - Background thread is sleeping (flush_interval not elapsed)

3. **Run Context Created**
   - `with run_context(run_id="abc-123")` entered
   - Creates `RunContext(run_id="abc-123", parent_id=None, depth=0)`
   - Pushes to thread-local stack
   - Sets `parent_event_id = "event-001"` (agent start event)

4. **Agent Function Executes**
   - `extract_expression()` runs (not tracked)
   - Returns "5 + 3"

5. **Tool Call Starts**
   - `calculator("5 + 3")` called
   - `@track_tool` decorator intercepts
   - Gets `run_id` from context = "abc-123" ✓
   - Gets `parent_event_id` from context = "event-001" ✓
   - Creates `ToolCallEvent`:
     ```python
     {
       "event_type": "tool_call",
       "run_id": "abc-123",  # From context
       "timestamp": "2024-01-15T10:30:01.000Z",
       "event_id": "event-002",
       "parent_event_id": "event-001",  # From context
       "data": {
         "tool_name": "calculator",
         "input": {"expression": "5 + 3"},
         "status": "started"
       }
     }
     ```
   - Calls `observe.track_event(tool_start_event)`

6. **Event Buffering (ToolCallEvent)**
   - Event enters `EventBuffer`
   - Buffer now contains 2 events
   - Still < 10, no flush

7. **Tool Executes**
   - `eval("5 + 3")` runs
   - Returns `8.0`
   - Execution time: 5ms

8. **Tool Call Ends**
   - Creates second `ToolCallEvent`:
     ```python
     {
       "event_type": "tool_call",
       "run_id": "abc-123",
       "timestamp": "2024-01-15T10:30:01.005Z",
       "event_id": "event-003",
       "parent_event_id": "event-001",
       "data": {
         "tool_name": "calculator",
         "output": {"result": 8.0},
         "latency_ms": 5.0,
         "status": "completed"
       }
     }
     ```
   - Buffered (3 events total)

9. **Agent Function Completes**
   - Returns "The answer is 8.0"
   - Total execution time: 100ms

10. **Agent Execution Ends**
    - `@track_agent` finally block executes
    - Creates `AgentEndEvent`:
      ```python
      {
        "event_type": "agent_end",
        "run_id": "abc-123",
        "timestamp": "2024-01-15T10:30:01.100Z",
        "event_id": "event-004",
        "data": {
          "output": {"result": "The answer is 8.0"},
          "total_duration_ms": 100.0,
          "total_cost": 0.0
        }
      }
      ```
    - Buffered (4 events total)

11. **Run Context Exits**
    - `with run_context()` exits
    - Pops `RunContext` from stack
    - Thread-local stack now empty

12. **Background Flush (Time-Based)**
    - 1 second elapses (flush_interval)
    - Background worker thread wakes up
    - Acquires lock
    - Checks if flush needed: yes (1s elapsed, 4 events in buffer)
    - Copies events: `[event-001, event-002, event-003, event-004]`
    - Clears buffer
    - Releases lock
    - Calls `flush_callback(events)` = `client.send_events(events)`

13. **HTTP Client Processing**
    - Converts events to dicts: `[e.to_dict() for e in events]`
    - Spawns background thread
    - Thread calls `_send_events_sync(events_dict)`
    - Wraps in batch: `{"events": [...]}`
    - Makes POST request:
      ```
      POST http://localhost:8000/api/events
      {
        "events": [
          {...AgentStartEvent...},
          {...ToolCallEvent (start)...},
          {...ToolCallEvent (end)...},
          {...AgentEndEvent...}
        ]
      }
      ```

14. **Retry Logic (if needed)**
    - If request fails with 500 error:
      - Waits 1 second (2^0)
      - Retries
    - If fails again:
      - Waits 2 seconds (2^1)
      - Retries
    - If fails third time:
      - Waits 4 seconds (2^2)
      - Retries
    - If still failing: gives up, logs error

15. **Success**
    - Backend responds with 200 OK
    - Events are persisted
    - Client thread exits
    - Main thread continues

**Event Relationships:**

The backend can now reconstruct the execution tree:

```
AgentStartEvent (event-001, run_id: abc-123)
├── ToolCallEvent (event-002, parent: event-001) [START]
└── ToolCallEvent (event-003, parent: event-001) [END]
AgentEndEvent (event-004, run_id: abc-123)
```

---

## Context Management & Run Tracking

### Thread-Local Storage Explained

**Problem:** How do we track context across function calls without passing parameters everywhere?

**Solution:** Thread-local storage - each thread has its own isolated context.

**Implementation:**

```python
class RunContextManager:
    _local = threading.local()  # Magic: each thread gets its own instance
```

**What `threading.local()` Does:**

When you access `_local.stack` from different threads:

```python
# Thread 1
_local.stack = [RunContext("run-1")]
print(_local.stack)  # [RunContext("run-1")]

# Thread 2 (running simultaneously)
_local.stack = [RunContext("run-2")]
print(_local.stack)  # [RunContext("run-2")]

# Back in Thread 1
print(_local.stack)  # Still [RunContext("run-1")] !
```

Each thread sees its own `stack` - they don't interfere.

**Why This Matters:**

- Supports concurrent agent execution (multiple agents running in different threads)
- Events from different threads don't get mixed up
- Each thread's run_id is independent

### Nested Contexts

**Example: Agent calls another agent**

```python
@track_agent
def research_agent(query):
    # This creates run context 1
    summary = summarize_agent(query)  # This creates run context 2
    return summary

@track_agent
def summarize_agent(text):
    # Uses nested context
    ...
```

**Stack Evolution:**

```
1. research_agent starts
   Stack: [RunContext(run_id="R1", parent_id=None, depth=0)]

2. summarize_agent starts
   Stack: [
     RunContext(run_id="R1", parent_id=None, depth=0),
     RunContext(run_id="R2", parent_id="R1", depth=1)  # New!
   ]

   get_current_run_id() → "R2"
   get_parent_run_id() → "R1"

3. summarize_agent ends
   Stack: [RunContext(run_id="R1", parent_id=None, depth=0)]  # Popped R2

4. research_agent ends
   Stack: []  # Popped R1
```

**Events Created:**

```
AgentStartEvent (run_id: R1, agent: research_agent)
├── AgentStartEvent (run_id: R2, agent: summarize_agent)
└── AgentEndEvent (run_id: R2, agent: summarize_agent)
AgentEndEvent (run_id: R1, agent: research_agent)
```

Backend can query: "Show me all events for R1 and its children" → Gets complete execution trace.

---

## Buffering & Network Communication

### Why Buffering?

**Without buffering:**
- Every event triggers an HTTP request
- Overhead: TCP handshake, TLS negotiation, HTTP headers
- 100 events = 100 HTTP requests = slow, wasteful

**With buffering:**
- Collect 10 events
- Send in 1 HTTP request
- 100 events = 10 HTTP requests = 10x faster

### Buffer Internals

**Thread Safety Pattern: Mutex Lock**

```python
def add_event(self, event):
    with self._lock:  # Only one thread can be inside this block at a time
        self._events.append(event)

        if len(self._events) >= self.batch_size:
            self._flush_locked()
```

**Why lock?**

Imagine two threads add events simultaneously without a lock:

```
Thread 1: Read len(self._events) → 9
Thread 2: Read len(self._events) → 9
Thread 1: Append event → [... 10 events]
Thread 2: Append event → [... 11 events] (oops, list corrupted!)
```

The lock ensures operations are **atomic** (all-or-nothing).

**Background Worker Pattern:**

```python
def _flush_worker(self):
    """Runs in background thread"""
    while not self._stop_event.is_set():
        # Sleep for flush_interval (default: 1 second)
        self._stop_event.wait(timeout=self.flush_interval)

        # Wake up, check if flush needed
        with self._lock:
            time_since_flush = time.time() - self._last_flush_time
            if time_since_flush >= self.flush_interval and self._events:
                self._flush_locked()
```

**Daemon Thread:**

```python
self._thread = threading.Thread(target=self._flush_worker, daemon=True)
```

`daemon=True` means: "If main program exits, kill this thread (don't wait for it)"

This prevents the buffer thread from keeping the program alive after user code finishes.

### Network Layer

**Connection Pooling:**

```python
self._session = requests.Session()
```

Session maintains a **pool of TCP connections**:
- First request to `localhost:8000`: Opens TCP connection, keeps it alive
- Second request: Reuses existing connection (much faster!)
- Automatically handles connection lifecycle

**Retry Strategy Details:**

| Attempt | Wait Time | Total Time Elapsed |
|---------|-----------|-------------------|
| 1       | 0s        | 0s                |
| 2       | 1s        | 1s                |
| 3       | 2s        | 3s                |
| 4       | 4s        | 7s                |

After 4 attempts over 7 seconds, gives up.

**Error Handling Philosophy:**

The SDK is designed to **never crash user code**:

```python
try:
    observe.track_event(event)
except Exception:
    pass  # Silent failure - tracking error doesn't stop agent
```

All tracking code is wrapped in try/except to ensure **fail-safe operation**.

---

## Class Structure Reference

### Directory Structure

```
sdk/gati/
├── __init__.py
├── observe.py                 # Main entry point (Observe class)
├── core/
│   ├── event.py              # Event dataclasses
│   ├── buffer.py             # EventBuffer (batching)
│   ├── client.py             # EventClient (HTTP)
│   ├── context.py            # RunContextManager (thread-local)
│   └── config.py             # Configuration
├── instrumentation/
│   ├── langchain.py          # LangChain callbacks + auto-inject
│   ├── langgraph.py          # LangGraph wrappers
│   ├── detector.py           # Auto-detect frameworks
│   └── base.py               # Base classes
├── decorators/
│   ├── track_agent.py        # @track_agent decorator
│   ├── track_tool.py         # @track_tool decorator
│   └── track_step.py         # @track_step decorator
└── utils/
    ├── serializer.py         # JSON serialization
    ├── token_counter.py      # Token counting
    ├── cost_calculator.py    # Cost calculation
    └── logger.py             # Logging utilities
```

### Key Classes Summary

| Class | File | Purpose | Pattern |
|-------|------|---------|---------|
| `Observe` | observe.py | Main SDK API | Singleton |
| `Event` (base) | core/event.py | Event data structure | Dataclass |
| `EventBuffer` | core/buffer.py | Event batching | Producer-Consumer |
| `EventClient` | core/client.py | HTTP communication | Connection Pool |
| `RunContextManager` | core/context.py | Context tracking | Thread-Local |
| `GatiLangChainCallback` | instrumentation/langchain.py | LangChain tracking | Callback Handler |
| `GatiStateGraphWrapper` | instrumentation/langgraph.py | LangGraph tracking | Wrapper |

### Configuration Options

```python
observe.init(
    backend_url="http://localhost:8000",  # Required
    api_key="sk-...",                      # Optional
    agent_name="my_agent",                 # Optional
    batch_size=10,                         # Events per batch
    flush_interval=1.0,                    # Seconds between flushes
    auto_inject=True,                      # Auto-inject LangChain callbacks
    environment="production",              # Environment tag
    telemetry=True,                        # Enable telemetry
)
```

---

## Complete Example: All Together

```python
from gati import observe
from gati.decorators import track_agent, track_tool
from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain.tools import tool

# 1. Initialize SDK
observe.init(
    backend_url="http://localhost:8000",
    agent_name="research_assistant",
    auto_inject=True  # Automatically track LangChain
)

# 2. Define custom tool with decorator
@track_tool
def calculate(expression: str) -> float:
    """Calculate a mathematical expression"""
    return eval(expression)

# 3. Create LangChain tool (auto-tracked via callbacks)
@tool
def search(query: str) -> str:
    """Search the web"""
    return f"Results for {query}..."

# 4. Create LangChain agent (auto-tracked via auto-inject)
llm = ChatOpenAI(model="gpt-4")
tools = [search, calculate]

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}")
])

agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools)

# 5. Custom agent orchestration with decorator
@track_agent(name="master_agent")
def master_agent(question: str) -> str:
    # LangChain agent execution (auto-tracked)
    result = executor.invoke({"input": question})

    # Custom processing (tracked as part of master_agent run)
    summary = result['output'][:100]

    return summary

# 6. Execute
answer = master_agent("What is the population of Tokyo and what's 5 + 3?")

# 7. Flush and shutdown
observe.flush()
observe.shutdown()
```

**Events Generated:**

```
AgentStartEvent (master_agent)
├── AgentStartEvent (LangChain executor) [auto-injected]
│   ├── LLMCallEvent (gpt-4) [via callback]
│   ├── ToolCallEvent (search) [via callback]
│   ├── LLMCallEvent (gpt-4) [via callback]
│   ├── ToolCallEvent (calculate) [via @track_tool]
│   ├── LLMCallEvent (gpt-4) [via callback]
│   └── AgentEndEvent (LangChain executor)
└── AgentEndEvent (master_agent)
```

All automatically tracked with proper parent-child relationships!

---

## Conclusion

The GATI SDK is a **layered observability system** that:

1. **Captures** execution data via instrumentation (callbacks, wrappers, decorators)
2. **Structures** data into typed events with metadata
3. **Contextualizes** events with run IDs and parent-child relationships
4. **Batches** events for efficient transmission
5. **Transmits** to backend via reliable HTTP with retries
6. **Fails safely** - never crashes user code

Each layer is designed with **separation of concerns**:
- Instrumentation knows how to intercept execution
- Events know how to represent data
- Context knows how to track relationships
- Buffer knows how to batch efficiently
- Client knows how to send reliably

This architecture makes the SDK:
- **Extensible** - Easy to add new frameworks
- **Reliable** - Fail-safe error handling
- **Performant** - Minimal overhead via batching and async
- **Developer-friendly** - Simple API, automatic instrumentation

You now have complete understanding and control over the SDK!
