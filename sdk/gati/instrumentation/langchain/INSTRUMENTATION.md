# LangChain Instrumentation - Comprehensive Implementation

## Overview

The GATI SDK now provides **comprehensive automatic instrumentation** for LangChain. Once enabled via `observe.init(auto_inject=True)`, all LangChain operations are automatically tracked without any code changes required.

## Features Implemented

### 1. Complete LLM Call Tracking

**What's tracked:**
- ✅ All LLM invocations (via `Runnable.invoke`, `BaseChatModel.invoke`)
- ✅ Direct LLM calls (via `BaseLanguageModel._generate` and `_call`)
- ✅ Both sync and async operations
- ✅ Streaming token accumulation via `on_llm_new_token`

**Captured data:**
- Model name (e.g., "gpt-3.5-turbo")
- System prompt and user prompt (separated)
- Completion text (including from streaming)
- Token usage (input/output tokens)
- Latency (milliseconds)
- Cost (calculated from model pricing)
- Status (success/error)
- **NEW:** Rich metadata:
  - Class name and module
  - Config parameters (temperature, max_tokens, top_p, etc.)
  - Invocation parameters

**Implementation:**
- Patched `Runnable.invoke/batch/stream` for all Runnables
- Patched `BaseChatModel.invoke` for chat models
- Patched `BaseLanguageModel._generate` for direct LLM calls
- Patched `BaseLanguageModel._call` for legacy LLM calls
- Enhanced callback handler with streaming support

### 2. Complete Tool Execution Tracking

**What's tracked:**
- ✅ All tool executions (via callback system)
- ✅ Direct tool calls (via `BaseTool._run` and `_arun`)
- ✅ `@tool` decorated functions
- ✅ Both sync and async tools

**Captured data:**
- Tool name
- Input parameters
- Output/result
- Latency (milliseconds)
- Status (success/error)
- **NEW:** Rich metadata:
  - Class name and module
  - Tool description
  - Arguments schema (from Pydantic models)
  - `return_direct` flag

**Implementation:**
- Existing callback handlers for `on_tool_start/end/error`
- **NEW:** Patched `BaseTool._run` for sync tool execution
- **NEW:** Patched `BaseTool._arun` for async tool execution
- Enhanced metadata extraction

### 3. Agent Workflow Tracking

**What's tracked:**
- ✅ AgentExecutor executions
- ✅ LangGraph agent graphs
- ✅ Start/end events with duration
- ✅ All nested LLM and tool calls

**Captured data:**
- Agent name
- Input/output
- Total duration
- Status
- All child events (LLM calls, tool executions)

**Implementation:**
- Smart agent detection via `_is_agent_runnable()`
- `AgentStartEvent` and `AgentEndEvent` creation
- Parent-child relationship tracking

### 4. Streaming Token Support

**What's tracked:**
- ✅ Individual tokens as they stream
- ✅ Complete response reconstruction
- ✅ Preserved metadata throughout streaming

**Implementation:**
- `on_llm_new_token` callback accumulates tokens
- Tokens stored in `_streaming_tokens` dict
- Final completion reconstructed from accumulated tokens
- Metadata preserved in `_streaming_metadata` dict

### 5. Parent-Child Event Relationships

**What's tracked:**
- ✅ Proper `run_id` propagation across all events
- ✅ `parent_event_id` linking for nested calls
- ✅ Context preservation in sync and async operations

**Implementation:**
- Context variables via `contextvars` (thread-safe and async-safe)
- `run_context()` and `arun_context()` managers
- Event ID mapping between LangChain and GATI
- Parent event ID propagation through callbacks

### 6. Enhanced Metadata for Debugging

**LLM Metadata:**
- Class name (e.g., "ChatOpenAI")
- Module (e.g., "langchain_openai.chat_models")
- Config parameters:
  - temperature
  - max_tokens
  - top_p, top_k
  - frequency_penalty, presence_penalty
  - n (number of completions)
  - stream flag

**Tool Metadata:**
- Class name (e.g., "StructuredTool")
- Module (e.g., "langchain.tools")
- Description (truncated to 200 chars)
- Arguments schema with properties and required fields
- `return_direct` flag

**Implementation:**
- `_extract_llm_metadata()` method in callback handler
- `_extract_tool_metadata()` method in callback handler
- Safe extraction with fallbacks for missing attributes

### 7. Version Compatibility

**Supported versions:**
- ✅ LangChain 0.1.x (legacy)
- ✅ LangChain 0.2.x
- ✅ LangChain 1.x (latest)

**Implementation:**
- Multiple import fallbacks for all classes
- Version-agnostic patching strategy
- Graceful degradation if classes not found

## Architecture

### Monkey Patching Strategy

```python
# Core patching happens in enable_auto_injection()
_patch_runnable_invoke()       # Patches Runnable methods
_patch_base_language_model()   # Patches LLM methods
_patch_base_tool()             # Patches Tool methods
```

### Callback Handler Enhancement

The `GatiLangChainCallback` class now includes:

```python
class GatiLangChainCallback(BaseCallbackHandler):
    def __init__(self):
        # Existing: timing, run_id mapping, event_id mapping
        # NEW: streaming token accumulation
        self._streaming_tokens: Dict[str, List[str]] = {}
        self._streaming_metadata: Dict[str, Dict[str, Any]] = {}

    # Existing callbacks
    def on_llm_start(...)
    def on_llm_end(...)
    def on_llm_error(...)
    def on_tool_start(...)
    def on_tool_end(...)
    def on_tool_error(...)

    # NEW: Streaming support
    def on_llm_new_token(self, token: str, **kwargs):
        """Accumulates streaming tokens"""
        ...

    # Enhanced metadata extraction
    def _extract_llm_metadata(...)
    def _extract_tool_metadata(...)
```

### Context Management

```python
# Sync context
with run_context() as run_id:
    # All events in this context share run_id
    llm.invoke("prompt")

# Async context
async with arun_context() as run_id:
    # Async-safe context management
    await llm.ainvoke("prompt")
```

## Usage

### Basic Setup

```python
from gati import observe

# Enable auto-injection (default)
observe.init(
    backend_url="http://localhost:8000",
    agent_name="my_agent",
    auto_inject=True  # This is the default
)

# Use LangChain normally - everything is tracked!
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-3.5-turbo")
response = llm.invoke("What is 2+2?")
```

### Streaming

```python
# Streaming tokens are automatically accumulated
for chunk in llm.stream("Tell me a story"):
    print(chunk.content, end="")

# GATI tracks:
# - Each token via on_llm_new_token
# - Complete response reconstructed
# - All metadata preserved
```

### Tools

```python
from langchain.tools import tool

@tool
def calculator(expression: str) -> str:
    """Evaluates a mathematical expression."""
    return str(eval(expression))

# Tool execution is automatically tracked
result = calculator.invoke("2 + 2")
```

### Agents

```python
from langchain.agents import AgentExecutor, create_tool_calling_agent

agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools)

# Agent execution is fully tracked:
# - AgentStartEvent
# - All LLM calls
# - All tool executions
# - AgentEndEvent
result = executor.invoke({"input": "Use the calculator to compute (5+3)*2"})
```

### Async Operations

```python
# Async operations work seamlessly
async def main():
    response = await llm.ainvoke("What is the capital of France?")
    return response

# All tracking works with async context management
```

## Event Structure

### LLMCallEvent

```json
{
  "event_type": "llm_call",
  "run_id": "uuid-here",
  "event_id": "uuid-here",
  "parent_event_id": "uuid-here",
  "model": "gpt-3.5-turbo",
  "prompt": "What is 2+2?",
  "system_prompt": "You are a helpful assistant",
  "completion": "2+2 equals 4.",
  "tokens_in": 15,
  "tokens_out": 8,
  "latency_ms": 234.5,
  "cost": 0.00012,
  "data": {
    "status": "completed",
    "llm_metadata": {
      "class_name": "ChatOpenAI",
      "module": "langchain_openai.chat_models",
      "config": {
        "temperature": 0.7,
        "max_tokens": 1000
      }
    }
  }
}
```

### ToolCallEvent

```json
{
  "event_type": "tool_call",
  "run_id": "uuid-here",
  "event_id": "uuid-here",
  "parent_event_id": "uuid-here",
  "tool_name": "calculator",
  "input": {"input_str": "2 + 2"},
  "output": {"output": "4"},
  "latency_ms": 12.3,
  "data": {
    "status": "completed",
    "tool_metadata": {
      "class_name": "StructuredTool",
      "module": "langchain.tools",
      "description": "Evaluates a mathematical expression.",
      "args_schema": {
        "properties": {
          "expression": {"type": "string"}
        },
        "required": ["expression"]
      }
    }
  }
}
```

### AgentStartEvent / AgentEndEvent

```json
{
  "event_type": "agent_start",
  "run_id": "uuid-here",
  "event_id": "uuid-here",
  "agent_name": "AgentExecutor",
  "input": {"input": "Compute (5+3)*2"},
  "metadata": {
    "auto_tracked": true,
    "runnable_type": "AgentExecutor"
  }
}
```

## Implementation Files

### Modified Files

1. **[auto_inject.py](auto_inject.py)**
   - Added `_patch_base_language_model()` function
   - Added `_patch_base_tool()` function
   - Updated `_patch_runnable_invoke()` to call new patch functions
   - Updated `_unpatch_runnable_invoke()` to restore new patches
   - Enhanced documentation

2. **[callback.py](callback.py)**
   - Added `_streaming_tokens` and `_streaming_metadata` dicts
   - Added `on_llm_new_token()` method for streaming support
   - Enhanced `on_llm_end()` to use streaming tokens
   - Added `_extract_llm_metadata()` method
   - Added `_extract_tool_metadata()` method
   - Updated cleanup logic to include streaming state

## Error Handling

All instrumentation code follows these principles:

1. **Never raise exceptions** - All patches wrapped in try/except
2. **Graceful degradation** - Missing classes/methods logged, not fatal
3. **Fail-safe fallbacks** - Original methods always callable
4. **Detailed logging** - Debug logs for all failures

Example:
```python
try:
    # Patch code
    BaseLanguageModel._generate = patched_generate
except Exception as e:
    logger.debug(f"Failed to patch BaseLanguageModel: {e}")
    # Continue without this patch
```

## Performance Impact

The instrumentation is designed to be lightweight:

- **No blocking operations** - All tracking is async/buffered
- **Minimal overhead** - Only metadata extraction and callback invocation
- **Memory efficient** - Cleanup of mappings after completion
- **Production ready** - Can be enabled in production with minimal impact

## Conclusion

The GATI SDK now provides **best-in-class LangChain instrumentation** with:

✅ **Complete coverage** - All LLM calls, tool executions, and agent workflows
✅ **Streaming support** - Token accumulation and reconstruction
✅ **Rich metadata** - Debugging information for all operations
✅ **Zero code changes** - Automatic instrumentation
✅ **Version compatible** - Works with LangChain 0.1.x, 0.2.x, and 1.x
✅ **Production ready** - Robust error handling and performance

Simply call `observe.init(auto_inject=True)` and start using LangChain - everything will be tracked automatically!
