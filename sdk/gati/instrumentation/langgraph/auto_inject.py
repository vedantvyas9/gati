"""LangGraph instrumentation for GATI - Simple Auto-Injection.

This module provides automatic instrumentation for LangGraph by monkey-patching
the StateGraph.compile() method. Once enabled, all LangGraph graphs are automatically
tracked without any code changes.

Usage:
    from gati import observe

    # Initialize - that's it! LangGraph graphs are auto-instrumented
    observe.init(backend_url="http://localhost:8000")

    # Use LangGraph normally - everything is tracked automatically
    from langgraph.graph import StateGraph

    graph = StateGraph(MyState)
    graph.add_node("node1", node1_func)
    graph.add_edge("node1", "node2")
    app = graph.compile()  # ← Automatically instrumented!

    result = app.invoke({"input": "..."})  # ← All execution tracked!

What gets tracked:
    Agent-Level:
    - Agent name, run start/end time, total duration
    - Overall status (success/error)
    - User input and final output
    - Error messages and traces if any

    Node-Level:
    - Node name, step start/end time, duration
    - Input & output state (full snapshots)
    - State changes (diffs showing what changed)
    - Node transitions (from → to)
    - Step status (ok/failed)
    - Function/class name executed
    - Node type (LLM, tool, subgraph, custom)
    - Errors with stack traces

    Plus:
    - All LLM calls within nodes (via LangChain instrumentation)
    - All tool invocations within nodes (via LangChain instrumentation)
    - Nested subgraph tracking with proper parent relationships
    - Custom logs and metrics
"""

from __future__ import annotations

import time
import logging
import dataclasses
import contextvars
import inspect
import traceback
from typing import Any, Dict, Optional, Callable

# Try importing LangGraph components
try:
    from langgraph.graph import StateGraph  # type: ignore
    from langgraph.pregel import Pregel  # type: ignore
    LANGGRAPH_AVAILABLE = True
except ImportError:
    StateGraph = None  # type: ignore
    Pregel = None  # type: ignore
    LANGGRAPH_AVAILABLE = False

from gati.observe import observe
from gati.core.event import (
    NodeExecutionEvent,
    AgentStartEvent,
    AgentEndEvent,
)
from gati.core.context import get_current_run_id, run_context, get_parent_event_id, set_parent_event_id
from gati.utils.serializer import serialize

logger = logging.getLogger("gati.langgraph")

# Context variable to prevent duplicate tracking when invoke() calls stream() internally
_in_graph_execution: contextvars.ContextVar[bool] = contextvars.ContextVar('_in_graph_execution', default=False)

# Context variable to track nested subgraph depth
_subgraph_depth: contextvars.ContextVar[int] = contextvars.ContextVar('_subgraph_depth', default=0)


def _extract_node_metadata(pregel: Any, node_name: str) -> Dict[str, Any]:
    """Extract rich metadata about a node.

    Extracts:
    - Function/class name that the node executes
    - Node type (LLM, tool, subgraph, custom function)
    - Module and file information

    Args:
        pregel: The Pregel graph instance
        node_name: Name of the node

    Returns:
        Dictionary with node metadata
    """
    metadata: Dict[str, Any] = {
        "node_name": node_name,
        "node_type": "unknown",
        "function_name": None,
        "class_name": None,
        "module": None,
        "file": None,
    }

    try:
        # Try to get node configuration from pregel
        if hasattr(pregel, "nodes") and isinstance(pregel.nodes, dict):
            node_spec = pregel.nodes.get(node_name)

            if node_spec:
                # Extract function/callable information
                node_callable = None

                # Different LangGraph versions have different structures
                if hasattr(node_spec, "func"):
                    node_callable = node_spec.func
                elif hasattr(node_spec, "runnable"):
                    node_callable = node_spec.runnable
                elif callable(node_spec):
                    node_callable = node_spec

                if node_callable:
                    # Determine node type
                    metadata["node_type"] = _determine_node_type(node_callable)

                    # Extract function/class name
                    if hasattr(node_callable, "__name__"):
                        metadata["function_name"] = node_callable.__name__

                    # Extract class name if it's a method
                    if hasattr(node_callable, "__self__"):
                        metadata["class_name"] = node_callable.__self__.__class__.__name__
                    elif inspect.ismethod(node_callable):
                        metadata["class_name"] = node_callable.__self__.__class__.__name__

                    # Extract module and file
                    if hasattr(node_callable, "__module__"):
                        metadata["module"] = node_callable.__module__

                    try:
                        source_file = inspect.getfile(node_callable)
                        metadata["file"] = source_file
                    except (TypeError, OSError):
                        pass

    except Exception as e:
        logger.debug(f"Failed to extract node metadata for {node_name}: {e}")

    return metadata


def _determine_node_type(node_callable: Any) -> str:
    """Determine the type of node based on the callable.

    Args:
        node_callable: The callable for the node

    Returns:
        Node type string: "llm", "tool", "subgraph", "chain", or "custom"
    """
    try:
        # Check class name and module for common patterns
        class_name = node_callable.__class__.__name__.lower() if hasattr(node_callable, "__class__") else ""
        module_name = node_callable.__module__.lower() if hasattr(node_callable, "__module__") else ""

        # Check for LLM
        if any(indicator in class_name for indicator in ["llm", "chatmodel", "openai", "anthropic", "claude", "gpt"]):
            return "llm"

        # Check for tool
        if any(indicator in class_name for indicator in ["tool", "structuredtool"]):
            return "tool"

        # Check for subgraph/nested graph
        if any(indicator in class_name for indicator in ["pregel", "stategraph", "compiledgraph", "graph"]):
            return "subgraph"

        # Check for chain
        if any(indicator in class_name for indicator in ["chain", "sequence", "runnable"]):
            return "chain"

        # Check if it's from langgraph (likely a graph node)
        if "langgraph" in module_name:
            return "graph_node"

        # Default to custom function
        return "custom"

    except Exception:
        return "unknown"


def _serialize_state(state: Any) -> Dict[str, Any]:
    """Serialize state to a JSON-safe dictionary."""
    try:
        return serialize(state)
    except Exception as e:
        logger.debug(f"Failed to serialize state: {e}")
        return {"error": f"Failed to serialize: {str(e)}"}


def _calculate_state_diff(state_before: Any, state_after: Any) -> Dict[str, Any]:
    """Calculate the difference between two states.

    Shows what changed between before and after, useful for understanding
    what each node did to the state.
    """
    try:
        diff: Dict[str, Any] = {}

        # Convert states to dictionaries
        before_dict: Dict[str, Any] = {}
        after_dict: Dict[str, Any] = {}

        if dataclasses.is_dataclass(state_before):
            before_dict = dataclasses.asdict(state_before)
        elif isinstance(state_before, dict):
            before_dict = state_before
        else:
            before_dict = {k: v for k, v in vars(state_before).items() if not k.startswith('_')} if hasattr(state_before, '__dict__') else {}

        if dataclasses.is_dataclass(state_after):
            after_dict = dataclasses.asdict(state_after)
        elif isinstance(state_after, dict):
            after_dict = state_after
        else:
            after_dict = {k: v for k, v in vars(state_after).items() if not k.startswith('_')} if hasattr(state_after, '__dict__') else {}

        # Compare and track changes
        all_keys = set(before_dict.keys()) | set(after_dict.keys())

        for key in all_keys:
            before_val = before_dict.get(key)
            after_val = after_dict.get(key)

            if before_val != after_val:
                diff[key] = {
                    'before': serialize(before_val),
                    'after': serialize(after_val),
                }

        return diff
    except Exception as e:
        logger.debug(f"Failed to calculate state diff: {e}")
        return {}


def _wrap_pregel(pregel: Any) -> Any:
    """Wrap a compiled Pregel instance to track execution.

    This wraps both invoke() and stream() methods to capture:
    - Graph-level execution (agent start/end events)
    - Node-level execution (node events with state diffs)
    - All LLM/tool calls (via LangChain instrumentation)
    - Nested subgraphs with proper parent-child relationships
    - Rich node metadata (function name, type, errors)
    """

    # Check if already wrapped
    if hasattr(pregel, '_gati_wrapped'):
        logger.debug("Pregel already wrapped, skipping")
        return pregel

    # Store original methods
    original_invoke = pregel.invoke
    original_stream = pregel.stream

    # Store a reference to the pregel for metadata extraction
    pregel_ref = pregel

    def wrapped_stream(input: Any, config: Optional[Dict] = None, **kwargs: Any):
        """Wrapped stream that tracks graph and node execution with LangChain integration."""

        # Check if we're already in a graph execution to prevent nested tracking
        already_in_execution = _in_graph_execution.get()

        if already_in_execution:
            # We're in a nested call (invoke calling stream), don't create new tracking
            for chunk in original_stream(input, config, **kwargs):
                yield chunk
            return

        # Set flag that we're in a graph execution
        token = _in_graph_execution.set(True)

        # Track subgraph depth
        current_depth = _subgraph_depth.get()
        depth_token = _subgraph_depth.set(current_depth + 1)
        is_nested_subgraph = current_depth > 0

        start_time = time.monotonic()
        error: Optional[Exception] = None
        all_chunks = []
        agent_start_event_id: Optional[str] = None
        last_state = input
        node_timings: Dict[str, float] = {}

        # Get parent run_id and parent_event_id if we're in a nested subgraph
        parent_run_id = get_current_run_id() if is_nested_subgraph else None
        parent_event_id = get_parent_event_id() if is_nested_subgraph else None

        # Create a new run context (or use parent's if nested)
        with run_context(parent_name=parent_run_id) as graph_run_id:
            try:
                # Inject LangChain callbacks for tracking LLM/tool calls within nodes
                if config is None:
                    config = {}

                # Add GATI callbacks if not already present
                if not config.get("callbacks"):
                    gati_callbacks = observe.get_callbacks()
                    if gati_callbacks:
                        config["callbacks"] = gati_callbacks

                # Track agent start
                # Don't set agent_name - let observe.track_event() use the configured agent_name
                start_event = AgentStartEvent(
                    run_id=graph_run_id,
                    input=_serialize_state(input),
                    metadata={
                        "graph_type": "langgraph",
                        "method": "stream",
                        "is_subgraph": is_nested_subgraph,
                        "depth": current_depth,
                        "parent_run_id": parent_run_id,
                    }
                )

                # Set parent relationship for nested subgraphs
                if parent_event_id:
                    start_event.parent_event_id = parent_event_id

                observe.track_event(start_event)
                agent_start_event_id = start_event.event_id
                set_parent_event_id(agent_start_event_id)

                # Stream and track each node execution
                for chunk in original_stream(input, config, **kwargs):
                    all_chunks.append(chunk)

                    # Track node executions from chunk
                    try:
                        if isinstance(chunk, dict):
                            items = chunk.items()
                        elif isinstance(chunk, tuple) and len(chunk) == 2:
                            items = [(chunk[0], chunk[1])]
                        else:
                            items = []

                        for node_name, node_output in items:
                            if node_name not in ("__start__", "__end__"):
                                node_start_time = node_timings.get(node_name, time.monotonic())
                                node_timings[node_name] = node_start_time
                                node_duration_ms = (time.monotonic() - node_start_time) * 1000.0

                                try:
                                    # Extract rich node metadata
                                    node_metadata = _extract_node_metadata(pregel_ref, node_name)

                                    # Create node execution event
                                    node_event = NodeExecutionEvent(
                                        run_id=graph_run_id,
                                        node_name=node_name,
                                        state_before=_serialize_state(last_state),
                                        state_after=_serialize_state(node_output),
                                        duration_ms=node_duration_ms,
                                        data={
                                            "node_name": node_name,
                                            "state_before": _serialize_state(last_state),
                                            "state_after": _serialize_state(node_output),
                                            "state_diff": _calculate_state_diff(last_state, node_output),
                                            "status": "completed",
                                            "metadata": node_metadata,
                                            "duration_ms": node_duration_ms,
                                        }
                                    )

                                    # Set parent relationship (graph start event is parent of all nodes)
                                    if agent_start_event_id:
                                        node_event.parent_event_id = agent_start_event_id

                                    observe.track_event(node_event)

                                    # Set this node as parent for any nested calls
                                    set_parent_event_id(node_event.event_id)

                                    last_state = node_output
                                except Exception as node_error:
                                    logger.error(
                                        f"Failed to track node '{node_name}': {node_error}",
                                        exc_info=True
                                    )

                                    # Track node failure event
                                    try:
                                        error_event = NodeExecutionEvent(
                                            run_id=graph_run_id,
                                            node_name=node_name,
                                            state_before=_serialize_state(last_state),
                                            state_after={},
                                            duration_ms=node_duration_ms,
                                            data={
                                                "node_name": node_name,
                                                "status": "error",
                                                "error": {
                                                    "type": type(node_error).__name__,
                                                    "message": str(node_error),
                                                    "traceback": traceback.format_exc(),
                                                },
                                                "duration_ms": node_duration_ms,
                                            }
                                        )
                                        if agent_start_event_id:
                                            error_event.parent_event_id = agent_start_event_id
                                        observe.track_event(error_event)
                                    except Exception:
                                        pass

                    except Exception as chunk_error:
                        logger.error(f"Failed to process chunk: {chunk_error}", exc_info=True)

                    yield chunk

            except Exception as e:
                error = e
                logger.error(f"Graph execution failed: {e}", exc_info=True)
                raise
            finally:
                # Reset the flags
                _in_graph_execution.reset(token)
                _subgraph_depth.reset(depth_token)

                # Track agent end
                try:
                    duration_ms = (time.monotonic() - start_time) * 1000.0
                    final_output = all_chunks[-1] if all_chunks else {}

                    end_event_data = {
                        "output": _serialize_state(final_output),
                        "total_duration_ms": duration_ms,
                        "chunks_count": len(all_chunks),
                        "status": "error" if error else "completed",
                        "is_subgraph": is_nested_subgraph,
                        "depth": current_depth,
                    }

                    if error:
                        end_event_data["error"] = {
                            "type": type(error).__name__,
                            "message": str(error),
                            "traceback": traceback.format_exc(),
                        }

                    end_event = AgentEndEvent(
                        run_id=graph_run_id,
                        output=end_event_data["output"],
                        total_duration_ms=duration_ms,
                    )

                    # Add additional metadata to the data dict
                    end_event.data.update({
                        "chunks_count": len(all_chunks),
                        "status": end_event_data["status"],
                        "is_subgraph": is_nested_subgraph,
                        "depth": current_depth,
                    })

                    if error:
                        end_event.data["error"] = end_event_data["error"]

                    # Set parent relationship for nested subgraphs (same parent as agent_start)
                    if parent_event_id:
                        end_event.parent_event_id = parent_event_id

                    observe.track_event(end_event)
                except Exception as tracking_error:
                    logger.error(f"Failed to track agent end: {tracking_error}", exc_info=True)

    def wrapped_invoke(input: Any, config: Optional[Dict] = None, **kwargs: Any) -> Any:
        """Wrapped invoke that uses stream internally with proper tracking and LangChain integration."""

        # Check if we're already in a graph execution
        already_in_execution = _in_graph_execution.get()

        if already_in_execution:
            # Nested call, just pass through
            return original_invoke(input, config, **kwargs)

        # Set flag
        token = _in_graph_execution.set(True)

        # Track subgraph depth
        current_depth = _subgraph_depth.get()
        depth_token = _subgraph_depth.set(current_depth + 1)
        is_nested_subgraph = current_depth > 0

        start_time = time.monotonic()
        error: Optional[Exception] = None
        agent_start_event_id: Optional[str] = None
        last_state = input
        node_timings: Dict[str, float] = {}

        # Get parent run_id and parent_event_id if we're in a nested subgraph
        parent_run_id = get_current_run_id() if is_nested_subgraph else None
        parent_event_id = get_parent_event_id() if is_nested_subgraph else None

        # Create a new run context (or use parent's if nested)
        with run_context(parent_name=parent_run_id) as graph_run_id:
            try:
                # Inject LangChain callbacks for tracking LLM/tool calls within nodes
                if config is None:
                    config = {}

                # Add GATI callbacks if not already present
                if not config.get("callbacks"):
                    gati_callbacks = observe.get_callbacks()
                    if gati_callbacks:
                        config["callbacks"] = gati_callbacks

                # Track agent start
                # Don't set agent_name - let observe.track_event() use the configured agent_name
                start_event = AgentStartEvent(
                    run_id=graph_run_id,
                    input=_serialize_state(input),
                    metadata={
                        "graph_type": "langgraph",
                        "method": "invoke",
                        "is_subgraph": is_nested_subgraph,
                        "depth": current_depth,
                        "parent_run_id": parent_run_id,
                    }
                )

                # Set parent relationship for nested subgraphs
                if parent_event_id:
                    start_event.parent_event_id = parent_event_id

                observe.track_event(start_event)
                agent_start_event_id = start_event.event_id
                set_parent_event_id(agent_start_event_id)

                # Track nodes by consuming stream
                for chunk in original_stream(input, config, **kwargs):
                    # Track node executions
                    try:
                        if isinstance(chunk, dict):
                            items = chunk.items()
                        elif isinstance(chunk, tuple) and len(chunk) == 2:
                            items = [(chunk[0], chunk[1])]
                        else:
                            items = []

                        for node_name, node_output in items:
                            if node_name not in ("__start__", "__end__"):
                                node_start_time = node_timings.get(node_name, time.monotonic())
                                node_timings[node_name] = node_start_time
                                node_duration_ms = (time.monotonic() - node_start_time) * 1000.0

                                try:
                                    # Extract rich node metadata
                                    node_metadata = _extract_node_metadata(pregel_ref, node_name)

                                    # Create node execution event
                                    node_event = NodeExecutionEvent(
                                        run_id=graph_run_id,
                                        node_name=node_name,
                                        state_before=_serialize_state(last_state),
                                        state_after=_serialize_state(node_output),
                                        duration_ms=node_duration_ms,
                                        data={
                                            "node_name": node_name,
                                            "state_before": _serialize_state(last_state),
                                            "state_after": _serialize_state(node_output),
                                            "state_diff": _calculate_state_diff(last_state, node_output),
                                            "status": "completed",
                                            "metadata": node_metadata,
                                            "duration_ms": node_duration_ms,
                                        }
                                    )

                                    # Set parent relationship (graph start event is parent of all nodes)
                                    if agent_start_event_id:
                                        node_event.parent_event_id = agent_start_event_id

                                    observe.track_event(node_event)

                                    # Set this node as parent for any nested calls
                                    set_parent_event_id(node_event.event_id)

                                    # Merge node output into last_state (accumulate changes)
                                    if isinstance(last_state, dict) and isinstance(node_output, dict):
                                        last_state = {**last_state, **node_output}
                                    else:
                                        last_state = node_output

                                except Exception as node_error:
                                    logger.error(
                                        f"Failed to track node '{node_name}': {node_error}",
                                        exc_info=True
                                    )

                                    # Track node failure event
                                    try:
                                        error_event = NodeExecutionEvent(
                                            run_id=graph_run_id,
                                            node_name=node_name,
                                            state_before=_serialize_state(last_state),
                                            state_after={},
                                            duration_ms=node_duration_ms,
                                            data={
                                                "node_name": node_name,
                                                "status": "error",
                                                "error": {
                                                    "type": type(node_error).__name__,
                                                    "message": str(node_error),
                                                    "traceback": traceback.format_exc(),
                                                },
                                                "duration_ms": node_duration_ms,
                                            }
                                        )
                                        if agent_start_event_id:
                                            error_event.parent_event_id = agent_start_event_id
                                        observe.track_event(error_event)
                                    except Exception:
                                        pass

                    except Exception as chunk_error:
                        logger.error(f"Failed to process chunk: {chunk_error}", exc_info=True)

                # Return the accumulated final state
                return last_state

            except Exception as e:
                error = e
                logger.error(f"Graph execution failed: {e}", exc_info=True)
                raise
            finally:
                # Reset flags
                _in_graph_execution.reset(token)
                _subgraph_depth.reset(depth_token)

                # Track agent end
                try:
                    duration_ms = (time.monotonic() - start_time) * 1000.0
                    end_event_data = {
                        "output": _serialize_state(last_state),
                        "total_duration_ms": duration_ms,
                        "status": "error" if error else "completed",
                        "is_subgraph": is_nested_subgraph,
                        "depth": current_depth,
                    }

                    if error:
                        end_event_data["error"] = {
                            "type": type(error).__name__,
                            "message": str(error),
                            "traceback": traceback.format_exc(),
                        }

                    end_event = AgentEndEvent(
                        run_id=graph_run_id,
                        output=end_event_data["output"],
                        total_duration_ms=duration_ms,
                    )

                    # Add additional metadata to the data dict
                    end_event.data.update({
                        "status": end_event_data["status"],
                        "is_subgraph": is_nested_subgraph,
                        "depth": current_depth,
                    })

                    if error:
                        end_event.data["error"] = end_event_data["error"]

                    # Set parent relationship for nested subgraphs (same parent as agent_start)
                    if parent_event_id:
                        end_event.parent_event_id = parent_event_id

                    observe.track_event(end_event)
                except Exception as tracking_error:
                    logger.error(f"Failed to track agent end: {tracking_error}", exc_info=True)

    # Replace methods
    pregel.invoke = wrapped_invoke
    pregel.stream = wrapped_stream

    # Mark as wrapped
    pregel._gati_wrapped = True

    return pregel


_instrumentation_applied = False
_original_compile = None


def instrument_langgraph() -> bool:
    """Enable automatic instrumentation for all LangGraph graphs.

    This function monkey-patches StateGraph.compile() to automatically wrap
    all compiled graphs. After calling this once (typically via observe.init()),
    all LangGraph usage is automatically tracked.

    Returns:
        bool: True if instrumentation succeeded, False otherwise
    """
    global _instrumentation_applied, _original_compile

    if not LANGGRAPH_AVAILABLE:
        logger.debug("LangGraph not installed")
        return False

    if _instrumentation_applied:
        logger.debug("LangGraph already instrumented")
        return True

    try:
        # Store original compile
        _original_compile = StateGraph.compile

        def instrumented_compile(self, *args: Any, **kwargs: Any) -> Any:
            """Instrumented compile that wraps the result."""
            try:
                compiled_graph = _original_compile(self, *args, **kwargs)
                wrapped_graph = _wrap_pregel(compiled_graph)
                return wrapped_graph
            except Exception as e:
                logger.debug(f"Failed to apply GATI instrumentation: {e}")
                return _original_compile(self, *args, **kwargs)

        # Replace compile method
        StateGraph.compile = instrumented_compile

        _instrumentation_applied = True
        logger.info("LangGraph instrumentation enabled")
        return True

    except Exception as e:
        logger.error(f"Failed to instrument LangGraph: {e}")
        return False


__all__ = ["instrument_langgraph"]
