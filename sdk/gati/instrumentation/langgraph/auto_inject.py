"""LangGraph instrumentation for GATI - Simple Auto-Injection.

This module provides automatic instrumentation for LangGraph by monkey-patching
the StateGraph.compile() method. Once enabled, all LangGraph graphs are automatically
tracked without any code changes.

Usage:
    from gati import observe

    # Initialize - that's it! LangGraph graphs are auto-instrumented
    observe.init(name="my_agent")

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
# Enable debug logging temporarily to diagnose edge extraction
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(levelname)s] %(name)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

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
    - Input/output channel names
    - Nested graph information

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
        "input_channels": [],
        "output_channels": [],
        "is_nested_graph": False,
        "nested_structure": None,
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

                    # Check if this is a nested graph/subgraph and extract its structure (depth-limited)
                    if metadata["node_type"] == "subgraph":
                        try:
                            if isinstance(node_callable, Pregel):
                                metadata["is_nested_graph"] = True
                                # Extract nested structure (recursively, but depth-limited)
                                nested = _extract_graph_structure(node_callable, depth_limit=2, current_depth=1)
                                metadata["nested_structure"] = nested
                        except Exception as nest_error:
                            logger.debug(f"Failed to extract nested graph structure for {node_name}: {nest_error}")

        # Try to extract input/output channels
        try:
            if hasattr(pregel, "input_channels"):
                channels = getattr(pregel, "input_channels", {})
                if isinstance(channels, dict):
                    metadata["input_channels"] = list(channels.keys())
                elif isinstance(channels, (list, set)):
                    metadata["input_channels"] = list(channels)

            if hasattr(pregel, "output_channels"):
                channels = getattr(pregel, "output_channels", {})
                if isinstance(channels, dict):
                    metadata["output_channels"] = list(channels.keys())
                elif isinstance(channels, (list, set)):
                    metadata["output_channels"] = list(channels)
        except Exception as ch_error:
            logger.debug(f"Failed to extract channels for {node_name}: {ch_error}")

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


def _analyze_execution_flow(execution_sequence: list) -> Dict[str, Any]:
    """Analyze the execution sequence to determine parallel vs sequential flow.

    Includes:
    - Total nodes executed
    - Execution order
    - Parallel execution groups (nodes whose time ranges overlap)
    - Sequential pairs (nodes that executed sequentially)
    - Latency gaps between sequential nodes
    - Concurrency ratio (parallel_nodes / total_nodes)
    - Node overlap groups (for better visualization of parallelism)

    Args:
        execution_sequence: List of execution records with start/end times

    Returns:
        Dictionary with comprehensive execution flow analysis
    """
    analysis: Dict[str, Any] = {
        "total_nodes_executed": len(execution_sequence),
        "execution_order": [item["node_name"] for item in execution_sequence],
        "parallel_groups": [],
        "sequential_pairs": [],
        "latency_gaps": [],
        "concurrency_ratio": 0.0,
        "node_overlap_groups": [],
    }

    try:
        # Detect parallel execution: nodes whose time ranges overlap
        for i, node1 in enumerate(execution_sequence):
            parallel_with = []
            for j, node2 in enumerate(execution_sequence):
                if i != j:
                    # Check if time ranges overlap
                    start1, end1 = node1["start_time"], node1["end_time"]
                    start2, end2 = node2["start_time"], node2["end_time"]

                    # Overlapping if: start1 < end2 AND start2 < end1
                    if start1 < end2 and start2 < end1:
                        parallel_with.append(node2["node_name"])

            if parallel_with:
                # Group parallel nodes together
                parallel_group = sorted([node1["node_name"]] + parallel_with)
                if parallel_group not in analysis["parallel_groups"]:
                    analysis["parallel_groups"].append(parallel_group)

        # Detect sequential pairs and calculate latency gaps
        for i in range(len(execution_sequence) - 1):
            current = execution_sequence[i]
            next_node = execution_sequence[i + 1]

            gap_ms = (next_node["start_time"] - current["end_time"]) * 1000.0

            # If current node ended before next started (with small tolerance)
            if current["end_time"] <= next_node["start_time"] + 0.001:  # 1ms tolerance
                analysis["sequential_pairs"].append([
                    current["node_name"],
                    next_node["node_name"]
                ])

                # Record latency gap between sequential nodes
                analysis["latency_gaps"].append({
                    "from": current["node_name"],
                    "to": next_node["node_name"],
                    "gap_ms": gap_ms,
                })

        # Calculate concurrency ratio: parallel_nodes / total_nodes
        # Count nodes that participate in parallel execution
        parallel_nodes_set = set()
        for group in analysis["parallel_groups"]:
            parallel_nodes_set.update(group)

        parallel_nodes_count = len(parallel_nodes_set)
        total_nodes = len(execution_sequence)

        if total_nodes > 0:
            analysis["concurrency_ratio"] = parallel_nodes_count / total_nodes
        else:
            analysis["concurrency_ratio"] = 0.0

        # Build node overlap groups (showing which nodes executed in parallel)
        # Group overlapping time windows
        sorted_nodes = sorted(execution_sequence, key=lambda x: x["start_time"])
        overlap_groups = []

        for node in sorted_nodes:
            node_name = node["node_name"]
            start = node["start_time"]
            end = node["end_time"]

            placed = False
            for group in overlap_groups:
                # Check if this node overlaps with any node in the group
                group_start = min(n["start_time"] for n in group)
                group_end = max(n["end_time"] for n in group)

                if start < group_end and end > group_start:
                    # Overlaps with this group
                    group.append(node)
                    placed = True
                    break

            if not placed:
                overlap_groups.append([node])

        # Convert overlap groups to list of node names
        analysis["node_overlap_groups"] = [
            [n["node_name"] for n in group]
            for group in overlap_groups
        ]

    except Exception as e:
        logger.debug(f"Failed to analyze execution flow: {e}")

    return analysis


def _ensure_json_serializable(obj: Any, depth: int = 0, max_depth: int = 5) -> Any:
    """Ensure an object is JSON-serializable, converting problematic types.

    This function safely converts objects to JSON-serializable forms, handling:
    - Callable objects (converted to string representation)
    - Complex types (converted to string)
    - Circular references (converted to placeholder)
    - Nested structures (recursively serialized with depth limit)

    Args:
        obj: The object to make JSON-serializable
        depth: Current recursion depth
        max_depth: Maximum recursion depth

    Returns:
        A JSON-serializable version of the object
    """
    try:
        # Import json to test serializability
        import json

        # Quick check: try to serialize directly
        if depth < max_depth:
            try:
                json.dumps(obj)
                return obj
            except (TypeError, ValueError):
                pass

        # Handle None
        if obj is None:
            return None

        # Handle primitives
        if isinstance(obj, (bool, int, float, str)):
            return obj

        # Handle bytes
        if isinstance(obj, (bytes, bytearray)):
            try:
                return obj.decode('utf-8')
            except Exception:
                return "<bytes>"

        # Handle callables - convert to string representation
        if callable(obj):
            try:
                # Try to get a meaningful name
                if hasattr(obj, "__name__"):
                    return f"<function {obj.__name__}>"
                elif hasattr(obj, "__class__"):
                    return f"<callable {obj.__class__.__name__}>"
                else:
                    return str(obj)
            except Exception:
                return "<callable>"

        # Handle dicts
        if isinstance(obj, dict):
            if depth >= max_depth:
                return "<dict>"
            return {
                _ensure_json_serializable(k, depth + 1, max_depth): _ensure_json_serializable(v, depth + 1, max_depth)
                for k, v in obj.items()
            }

        # Handle lists, tuples, sets
        if isinstance(obj, (list, tuple, set)):
            if depth >= max_depth:
                return f"<{type(obj).__name__}>"
            return [_ensure_json_serializable(item, depth + 1, max_depth) for item in obj]

        # Handle other objects - try to convert to dict
        if hasattr(obj, "__dict__"):
            if depth >= max_depth:
                return str(obj)
            try:
                return {
                    k: _ensure_json_serializable(v, depth + 1, max_depth)
                    for k, v in obj.__dict__.items()
                    if not k.startswith("_")
                }
            except Exception:
                return str(obj)

        # Fallback: convert to string
        return str(obj)

    except Exception as e:
        logger.debug(f"Failed to ensure JSON serializability: {e}")
        return "<unserializable>"


def _extract_graph_structure(
    pregel: Any,
    depth_limit: int = 3,
    current_depth: int = 0
) -> Dict[str, Any]:
    """Extract the graph structure from a Pregel instance.

    Extracts with rich metadata:
    - All nodes with detailed metadata (type, function, channels, nested structure)
    - Edges with rich metadata (type, condition, async, module, file)
    - Entry point and end nodes
    - Conditional edge information
    - Optional nested graph structure (depth-limited to prevent infinite recursion)

    Args:
        pregel: The Pregel graph instance
        depth_limit: Maximum recursion depth for nested graphs (default: 3)
        current_depth: Current recursion depth (internal use)

    Returns:
        Dictionary with comprehensive graph structure information
    """
    structure: Dict[str, Any] = {
        "nodes": [],
        "nodes_metadata": {},
        "edges": [],
        "entry_point": None,
        "end_nodes": [],
        "has_conditional_edges": False,
        "total_nodes": 0,
        "total_edges": 0,
        "conditional_edge_count": 0,
    }

    # Prevent deep recursion for nested graphs
    if current_depth >= depth_limit:
        logger.debug(f"Graph structure extraction reached depth limit ({depth_limit})")
        return structure

    try:
        # Extract nodes with full metadata
        if hasattr(pregel, "nodes") and isinstance(pregel.nodes, dict):
            node_list = list(pregel.nodes.keys())
            structure["nodes"] = node_list

            # Extract rich metadata for each node
            for node_name in node_list:
                try:
                    node_metadata = _extract_node_metadata(pregel, node_name)
                    structure["nodes_metadata"][node_name] = node_metadata
                except Exception as node_error:
                    logger.debug(f"Failed to extract metadata for node {node_name}: {node_error}")
                    structure["nodes_metadata"][node_name] = {
                        "node_name": node_name,
                        "node_type": "unknown"
                    }

        # Extract edges from channels/graph structure with rich metadata
        edges = []
        edges_with_metadata: Dict[str, Any] = {}

        # DEBUG: Log pregel attributes to help diagnose edge extraction
        # logger.debug(f"Pregel type: {type(pregel).__name__}")
        # logger.debug(f"Pregel attributes: {[attr for attr in dir(pregel) if not attr.startswith('_')]}")

        # Method 1: Try _edges attribute directly
        edge_extraction_methods_tried = []
        if hasattr(pregel, "_edges"):
            edge_extraction_methods_tried.append("pregel._edges")
            try:
                pregel_edges = pregel._edges
                # logger.debug(f"Found pregel._edges: {type(pregel_edges)}, content: {pregel_edges}")
                if isinstance(pregel_edges, dict):
                    for source, targets in pregel_edges.items():
                        if isinstance(targets, (list, tuple, set)):
                            for target in targets:
                                edges.append({
                                    "from": source,
                                    "to": target,
                                    "type": "regular",
                                    "condition": None,
                                    "condition_func": None,
                                    "async": False,
                                    "module": None,
                                    "file": None,
                                })
                        elif isinstance(targets, dict):
                            # Conditional edges
                            structure["has_conditional_edges"] = True
                            for condition, target in targets.items():
                                condition_func_name = None
                                condition_module = None
                                condition_file = None
                                is_async = False
                                try:
                                    if callable(condition):
                                        condition_func_name = getattr(condition, "__name__", None)
                                        condition_module = getattr(condition, "__module__", None)
                                        try:
                                            condition_file = inspect.getfile(condition)
                                        except (TypeError, OSError):
                                            pass
                                        is_async = inspect.iscoroutinefunction(condition)
                                except Exception:
                                    pass
                                edges.append({
                                    "from": source,
                                    "to": target,
                                    "type": "conditional",
                                    "condition": _ensure_json_serializable(condition),
                                    "condition_func": condition_func_name,
                                    "async": is_async,
                                    "module": condition_module,
                                    "file": condition_file,
                                })
                                structure["conditional_edge_count"] += 1
                # logger.debug(f"Extracted {len(edges)} edges from pregel._edges")
            except Exception as e:
                # logger.debug(f"Failed to extract edges from pregel._edges: {e}")
                pass

        # Method 2: Try builder edges (StateGraph builder)
        if not edges and hasattr(pregel, "builder"):
            edge_extraction_methods_tried.append("pregel.builder")
            # logger.debug(f"Found pregel.builder: {type(pregel.builder)}")

            # Try multiple builder attributes
            builder = pregel.builder

            # Try _all_edges (newer LangGraph)
            if hasattr(builder, "_all_edges"):
                edge_extraction_methods_tried.append("pregel.builder._all_edges")
                try:
                    all_edges = builder._all_edges
                    # logger.debug(f"Found pregel.builder._all_edges: {type(all_edges)}, content: {all_edges}")
                    # _all_edges can be a set, list, or tuple
                    edge_collection = list(all_edges) if isinstance(all_edges, (set, list, tuple)) else []
                    for edge_spec in edge_collection:
                        # edge_spec might be tuple (source, target) or dict
                        if isinstance(edge_spec, tuple) and len(edge_spec) >= 2:
                            source, target = edge_spec[0], edge_spec[1]
                            edges.append({
                                "from": source,
                                "to": target if target != "__end__" else "__end__",
                                "type": "regular",
                                "condition": None,
                                "condition_func": None,
                                "async": False,
                                "module": None,
                                "file": None,
                            })
                        elif isinstance(edge_spec, dict):
                            source = edge_spec.get("source") or edge_spec.get("from")
                            target = edge_spec.get("target") or edge_spec.get("to")
                            if source and target:
                                edges.append({
                                    "from": source,
                                    "to": target if target != "__end__" else "__end__",
                                    "type": edge_spec.get("type", "regular"),
                                    "condition": edge_spec.get("condition"),
                                    "condition_func": None,
                                    "async": False,
                                    "module": None,
                                    "file": None,
                                })
                    # logger.debug(f"Extracted {len(edges)} edges from pregel.builder._all_edges")
                except Exception as e:
                    # logger.debug(f"Failed to extract edges from pregel.builder._all_edges: {e}")
                    pass

            # Try _edges
            if not edges and hasattr(builder, "_edges"):
                edge_extraction_methods_tried.append("pregel.builder._edges")
                try:
                    builder_edges = builder._edges
                    # logger.debug(f"Found pregel.builder._edges: {type(builder_edges)}, content: {builder_edges}")
                    if isinstance(builder_edges, dict):
                        for source, targets in builder_edges.items():
                            if isinstance(targets, (list, tuple, set)):
                                for target in targets:
                                    edges.append({
                                        "from": source,
                                        "to": target if target != "END" else "__end__",
                                        "type": "regular",
                                        "condition": None,
                                        "condition_func": None,
                                        "async": False,
                                        "module": None,
                                        "file": None,
                                    })
                            elif isinstance(targets, dict):
                                structure["has_conditional_edges"] = True
                                for condition, target in targets.items():
                                    condition_func_name = None
                                    condition_module = None
                                    condition_file = None
                                    is_async = False
                                    try:
                                        if callable(condition):
                                            condition_func_name = getattr(condition, "__name__", None)
                                            condition_module = getattr(condition, "__module__", None)
                                            try:
                                                condition_file = inspect.getfile(condition)
                                            except (TypeError, OSError):
                                                pass
                                            is_async = inspect.iscoroutinefunction(condition)
                                    except Exception:
                                        pass
                                    edges.append({
                                        "from": source,
                                        "to": target if target != "END" else "__end__",
                                        "type": "conditional",
                                        "condition": _ensure_json_serializable(condition),
                                        "condition_func": condition_func_name,
                                        "async": is_async,
                                        "module": condition_module,
                                        "file": condition_file,
                                    })
                                    structure["conditional_edge_count"] += 1
                            elif targets == "END":
                                edges.append({
                                    "from": source,
                                    "to": "__end__",
                                    "type": "regular",
                                    "condition": None,
                                    "condition_func": None,
                                    "async": False,
                                    "module": None,
                                    "file": None,
                                })
                            elif isinstance(targets, str):
                                edges.append({
                                    "from": source,
                                    "to": targets if targets != "END" else "__end__",
                                    "type": "regular",
                                    "condition": None,
                                    "condition_func": None,
                                    "async": False,
                                    "module": None,
                                    "file": None,
                                })
                    # logger.debug(f"Extracted {len(edges)} edges from pregel.builder._edges")
                except Exception as e:
                    # logger.debug(f"Failed to extract edges from pregel.builder._edges: {e}")
                    pass

            # Try entry_point
            if hasattr(builder, "_entry_point") or hasattr(builder, "entry_point"):
                entry = getattr(builder, "_entry_point", None) or getattr(builder, "entry_point", None)
                if entry:
                    # logger.debug(f"Found builder entry_point: {entry}")
                    # Add edge from __start__ to entry point
                    if not any(e["from"] == "__start__" and e["to"] == entry for e in edges):
                        edges.append({
                            "from": "__start__",
                            "to": entry,
                            "type": "regular",
                            "condition": None,
                            "condition_func": None,
                            "async": False,
                            "module": None,
                            "file": None,
                        })
                        # logger.debug(f"Added __start__ -> {entry} edge from entry_point")

        # Method 3: Try channels structure (newer LangGraph versions)
        if not edges and hasattr(pregel, "channels"):
            edge_extraction_methods_tried.append("pregel.channels")
            try:
                channels = pregel.channels
                # logger.debug(f"Found pregel.channels: {type(channels)}, keys: {list(channels.keys()) if isinstance(channels, dict) else 'not a dict'}")
                # In newer LangGraph, edges might be stored differently
                # Try to look for graph attribute
                if hasattr(pregel, "graph"):
                    edge_extraction_methods_tried.append("pregel.graph")
                    graph = pregel.graph
                    # logger.debug(f"Found pregel.graph: {type(graph)}, attributes: {[attr for attr in dir(graph) if not attr.startswith('_')]}")

                    # Try different edge attributes on the graph
                    for edge_attr in ["edges", "_edges", "edge_list", "_edge_list"]:
                        if hasattr(graph, edge_attr):
                            edge_extraction_methods_tried.append(f"pregel.graph.{edge_attr}")
                            try:
                                graph_edges = getattr(graph, edge_attr)
                                # logger.debug(f"Found pregel.graph.{edge_attr}: {type(graph_edges)}, content: {graph_edges}")
                                if isinstance(graph_edges, (list, tuple)):
                                    for edge in graph_edges:
                                        if isinstance(edge, dict):
                                            edges.append({
                                                "from": edge.get("source", edge.get("from", "unknown")),
                                                "to": edge.get("target", edge.get("to", "unknown")),
                                                "type": edge.get("type", "regular"),
                                                "condition": edge.get("condition"),
                                                "condition_func": None,
                                                "async": edge.get("async", False),
                                                "module": None,
                                                "file": None,
                                            })
                                        elif hasattr(edge, "source") and hasattr(edge, "target"):
                                            edges.append({
                                                "from": edge.source,
                                                "to": edge.target,
                                                "type": getattr(edge, "type", "regular"),
                                                "condition": getattr(edge, "condition", None),
                                                "condition_func": None,
                                                "async": getattr(edge, "async", False),
                                                "module": None,
                                                "file": None,
                                            })
                                elif isinstance(graph_edges, dict):
                                    for source, targets in graph_edges.items():
                                        if isinstance(targets, (list, tuple, set)):
                                            for target in targets:
                                                edges.append({
                                                    "from": source,
                                                    "to": target,
                                                    "type": "regular",
                                                    "condition": None,
                                                    "condition_func": None,
                                                    "async": False,
                                                    "module": None,
                                                    "file": None,
                                                })
                                # logger.debug(f"Extracted {len(edges)} edges from pregel.graph.{edge_attr}")
                                if edges:
                                    break
                            except Exception as e:
                                # logger.debug(f"Failed to extract from pregel.graph.{edge_attr}: {e}")
                                pass
            except Exception as e:
                # logger.debug(f"Failed to extract edges from channels structure: {e}")
                pass

        # Method 4: Try trigger_to_nodes mapping (newer LangGraph versions)
        if not edges and hasattr(pregel, "trigger_to_nodes"):
            edge_extraction_methods_tried.append("pregel.trigger_to_nodes")
            try:
                trigger_to_nodes = pregel.trigger_to_nodes
                # logger.debug(f"Found pregel.trigger_to_nodes: {type(trigger_to_nodes)}, content: {trigger_to_nodes}")

                # In newer LangGraph, we need to find which nodes write to which trigger channels
                # Build a mapping of: trigger_channel -> nodes that write to it
                trigger_writers = {}

                if hasattr(pregel, "nodes") and isinstance(pregel.nodes, dict):
                    for node_name, node_obj in pregel.nodes.items():
                        # Check if node has writers attribute (channels it writes to)
                        if hasattr(node_obj, "writers"):
                            writers = getattr(node_obj, "writers", [])
                            # logger.debug(f"Node '{node_name}' writes to: {writers}")
                            # Build reverse mapping: which triggers does this node activate?
                            if isinstance(writers, (list, tuple)):
                                for writer in writers:
                                    # writer might be a channel object or dict with 'channel' key
                                    channel_name = None
                                    if isinstance(writer, dict) and "channel" in writer:
                                        channel_name = writer["channel"]
                                    elif isinstance(writer, str):
                                        channel_name = writer
                                    elif hasattr(writer, "channel"):
                                        channel_name = getattr(writer, "channel")
                                    elif hasattr(writer, "name"):
                                        channel_name = getattr(writer, "name")

                                    if channel_name:
                                        if channel_name not in trigger_writers:
                                            trigger_writers[channel_name] = []
                                        trigger_writers[channel_name].append(node_name)

                        # Also check flat_writers
                        if hasattr(node_obj, "flat_writers"):
                            flat_writers = getattr(node_obj, "flat_writers")
                            # logger.debug(f"Node '{node_name}' has flat_writers (type: {type(flat_writers)})")
                            if isinstance(flat_writers, (list, tuple)):
                                for writer in flat_writers:
                                    channel_name = None
                                    if isinstance(writer, dict):
                                        channel_name = writer.get("channel") or writer.get("name")
                                    elif isinstance(writer, str):
                                        channel_name = writer
                                    elif hasattr(writer, "channel"):
                                        channel_name = getattr(writer, "channel")
                                    elif hasattr(writer, "name"):
                                        channel_name = getattr(writer, "name")

                                    if channel_name:
                                        if channel_name not in trigger_writers:
                                            trigger_writers[channel_name] = []
                                        if node_name not in trigger_writers[channel_name]:
                                            trigger_writers[channel_name].append(node_name)

                # logger.debug(f"Trigger writers mapping: {trigger_writers}")

                # Now build edges: for each trigger channel, connect writers to targets
                if isinstance(trigger_to_nodes, dict):
                    for trigger_channel, target_nodes in trigger_to_nodes.items():
                        # logger.debug(f"Trigger channel '{trigger_channel}' activates nodes: {target_nodes}")

                        # Find which nodes write to this trigger
                        source_nodes = trigger_writers.get(trigger_channel, [])

                        # If no explicit writers found, try to infer from channel name
                        if not source_nodes:
                            if trigger_channel == "__start__":
                                source_nodes = ["__start__"]
                            elif trigger_channel.startswith("branch:to:"):
                                # This is likely written by a routing/conditional node
                                # Try to find the source in the builder if available
                                pass

                        # Create edges from each source to each target
                        targets = target_nodes if isinstance(target_nodes, (list, tuple, set)) else [target_nodes]
                        for target in targets:
                            if source_nodes:
                                for source in source_nodes:
                                    edges.append({
                                        "from": source,
                                        "to": target,
                                        "type": "regular",
                                        "condition": None,
                                        "condition_func": None,
                                        "async": False,
                                        "module": None,
                                        "file": None,
                                    })
                            else:
                                # No source found - try to infer from trigger name
                                if trigger_channel.startswith("branch:to:"):
                                    inferred_source = trigger_channel.replace("branch:to:", "")
                                    edges.append({
                                        "from": inferred_source,
                                        "to": target,
                                        "type": "regular",
                                        "condition": None,
                                        "condition_func": None,
                                        "async": False,
                                        "module": None,
                                        "file": None,
                                    })

                    # logger.debug(f"Extracted {len(edges)} edges from pregel.trigger_to_nodes")
            except Exception as e:
                # logger.debug(f"Failed to extract edges from trigger_to_nodes: {e}")
                # logger.debug(f"Traceback: {traceback.format_exc()}")
                pass

        # Method 5: Try nodes attribute for edge connections (fallback)
        if not edges and hasattr(pregel, "nodes") and isinstance(pregel.nodes, dict):
            edge_extraction_methods_tried.append("pregel.nodes connections")
            try:
                for node_name, node_obj in pregel.nodes.items():
                    # logger.debug(f"Examining node '{node_name}': {type(node_obj)}, attributes: {[attr for attr in dir(node_obj) if not attr.startswith('_')][:10]}")
                    # Try to find outgoing edges from the node
                    for edge_attr in ["triggers", "next", "edges", "connections", "outputs"]:
                        if hasattr(node_obj, edge_attr):
                            try:
                                targets = getattr(node_obj, edge_attr)
                                # logger.debug(f"Node '{node_name}' has {edge_attr}: {targets}")
                                if isinstance(targets, (list, tuple, set)):
                                    for target in targets:
                                        edges.append({
                                            "from": node_name,
                                            "to": target,
                                            "type": "regular",
                                            "condition": None,
                                            "condition_func": None,
                                            "async": False,
                                            "module": None,
                                            "file": None,
                                        })
                                elif isinstance(targets, dict):
                                    for condition, target in targets.items():
                                        edges.append({
                                            "from": node_name,
                                            "to": target,
                                            "type": "conditional",
                                            "condition": _ensure_json_serializable(condition),
                                            "condition_func": getattr(condition, "__name__", None) if callable(condition) else None,
                                            "async": False,
                                            "module": None,
                                            "file": None,
                                        })
                                elif isinstance(targets, str):
                                    edges.append({
                                        "from": node_name,
                                        "to": targets,
                                        "type": "regular",
                                        "condition": None,
                                        "condition_func": None,
                                        "async": False,
                                        "module": None,
                                        "file": None,
                                    })
                            except Exception as e:
                                # logger.debug(f"Failed to extract {edge_attr} from node '{node_name}': {e}")
                                pass
                # logger.debug(f"Extracted {len(edges)} edges from node connections")
            except Exception as e:
                # logger.debug(f"Failed to extract edges from nodes: {e}")
                pass

        # Log which methods were tried
        # logger.debug(f"Edge extraction methods tried: {edge_extraction_methods_tried}")
        # logger.debug(f"Total edges found so far: {len(edges)}")
        # if edges:
        #     logger.debug(f"Edge details: {[(e['from'], e['to'], e['type']) for e in edges]}")

        # Deduplicate edges
        unique_edges = {}
        for edge in edges:
            key = (edge["from"], edge["to"], edge["type"])
            if key not in unique_edges:
                unique_edges[key] = edge

        structure["edges"] = list(unique_edges.values())

        # Try to find entry point
        if hasattr(pregel, "input_channels"):
            # The entry point is typically the first node that receives input
            structure["entry_point"] = structure["nodes"][0] if structure["nodes"] else None

        # Try to find end nodes (nodes that lead to END)
        end_nodes = []
        for edge in structure["edges"]:
            if edge.get("to") in ("__end__", "END", None):
                if edge.get("from") not in end_nodes:
                    end_nodes.append(edge.get("from"))
        structure["end_nodes"] = end_nodes

        # Set totals
        structure["total_nodes"] = len(structure["nodes"])
        structure["total_edges"] = len(structure["edges"])

        # Log extraction summary
        # conditional_count = structure["conditional_edge_count"]
        # logger.debug(
        #     f"Extracted graph structure: {structure['total_nodes']} nodes, "
        #     f"{structure['total_edges']} edges ({conditional_count} conditional)"
        # )

    except Exception as e:
        # logger.debug(f"Failed to extract graph structure: {e}")
        # logger.debug(f"Traceback: {traceback.format_exc()}")
        pass

    # Ensure all structure data is JSON-serializable
    try:
        structure = _ensure_json_serializable(structure)
        # logger.debug("Graph structure is JSON-serializable")
    except Exception as serialization_error:
        logger.warning(f"Warning: Graph structure contains non-serializable data: {serialization_error}")

    return structure


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
        last_node_event_id: Optional[str] = None  # Track last executed node
        previous_event_id: Optional[str] = None  # Track previous event for sequential flow
        last_state = input
        node_timings: Dict[str, float] = {}
        execution_sequence: list = []  # Track the actual execution sequence
        node_start_times: Dict[str, float] = {}  # Track when each node started
        node_end_times: Dict[str, float] = {}  # Track when each node ended

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

                # Extract graph structure
                graph_structure = _extract_graph_structure(pregel_ref)

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
                        "graph_structure": graph_structure,
                    }
                )

                # Set parent relationship for nested subgraphs
                if parent_event_id:
                    start_event.parent_event_id = parent_event_id

                observe.track_event(start_event)
                agent_start_event_id = start_event.event_id
                previous_event_id = agent_start_event_id  # AgentStart is the first event in sequence
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
                                # Track node execution timing
                                if node_name not in node_start_times:
                                    node_start_times[node_name] = time.monotonic()

                                node_end_times[node_name] = time.monotonic()
                                node_duration_ms = (node_end_times[node_name] - node_start_times[node_name]) * 1000.0

                                # Add to execution sequence
                                execution_sequence.append({
                                    "node_name": node_name,
                                    "start_time": node_start_times[node_name],
                                    "end_time": node_end_times[node_name],
                                    "sequence_index": len(execution_sequence)
                                })

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
                                            "sequence_index": len(execution_sequence) - 1,  # Position in execution order
                                        }
                                    )

                                    # Set parent relationship (graph start event is parent of all nodes)
                                    if agent_start_event_id:
                                        node_event.parent_event_id = agent_start_event_id

                                    # Set sequential flow relationship
                                    if previous_event_id:
                                        node_event.previous_event_id = previous_event_id

                                    observe.track_event(node_event)

                                    # Set this node as parent for any nested calls
                                    set_parent_event_id(node_event.event_id)

                                    # Track this as the last executed node and update sequential chain
                                    last_node_event_id = node_event.event_id
                                    previous_event_id = node_event.event_id

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

                    # Analyze execution flow
                    execution_flow = _analyze_execution_flow(execution_sequence)

                    # Add additional metadata to the data dict
                    end_event.data.update({
                        "chunks_count": len(all_chunks),
                        "status": end_event_data["status"],
                        "is_subgraph": is_nested_subgraph,
                        "depth": current_depth,
                        "execution_flow": execution_flow,
                        "execution_sequence": [
                            {
                                "node_name": item["node_name"],
                                "sequence_index": item["sequence_index"],
                                "duration_ms": (item["end_time"] - item["start_time"]) * 1000.0
                            }
                            for item in execution_sequence
                        ],
                        "graph_structure": graph_structure,
                    })

                    if error:
                        end_event.data["error"] = end_event_data["error"]

                    # Set parent relationship - connect to last executed node to show flow
                    # For nested subgraphs, still use the parent_event_id
                    if is_nested_subgraph and parent_event_id:
                        end_event.parent_event_id = parent_event_id
                    elif last_node_event_id:
                        end_event.parent_event_id = last_node_event_id
                    elif agent_start_event_id:
                        # Fallback to agent start if no nodes executed
                        end_event.parent_event_id = agent_start_event_id

                    # Set sequential flow relationship
                    if previous_event_id:
                        end_event.previous_event_id = previous_event_id

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
        last_node_event_id: Optional[str] = None  # Track last executed node
        previous_event_id: Optional[str] = None  # Track previous event for sequential flow
        last_state = input
        node_timings: Dict[str, float] = {}
        execution_sequence: list = []  # Track the actual execution sequence
        node_start_times: Dict[str, float] = {}  # Track when each node started
        node_end_times: Dict[str, float] = {}  # Track when each node ended

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

                # Extract graph structure
                graph_structure = _extract_graph_structure(pregel_ref)

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
                        "graph_structure": graph_structure,
                    }
                )

                # Set parent relationship for nested subgraphs
                if parent_event_id:
                    start_event.parent_event_id = parent_event_id

                observe.track_event(start_event)
                agent_start_event_id = start_event.event_id
                previous_event_id = agent_start_event_id  # AgentStart is the first event in sequence
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
                                # Track node execution timing
                                if node_name not in node_start_times:
                                    node_start_times[node_name] = time.monotonic()

                                node_end_times[node_name] = time.monotonic()
                                node_duration_ms = (node_end_times[node_name] - node_start_times[node_name]) * 1000.0

                                # Add to execution sequence
                                execution_sequence.append({
                                    "node_name": node_name,
                                    "start_time": node_start_times[node_name],
                                    "end_time": node_end_times[node_name],
                                    "sequence_index": len(execution_sequence)
                                })

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
                                            "sequence_index": len(execution_sequence) - 1,  # Position in execution order
                                        }
                                    )

                                    # Set parent relationship (graph start event is parent of all nodes)
                                    if agent_start_event_id:
                                        node_event.parent_event_id = agent_start_event_id

                                    # Set sequential flow relationship
                                    if previous_event_id:
                                        node_event.previous_event_id = previous_event_id

                                    observe.track_event(node_event)

                                    # Set this node as parent for any nested calls
                                    set_parent_event_id(node_event.event_id)

                                    # Track this as the last executed node and update sequential chain
                                    last_node_event_id = node_event.event_id
                                    previous_event_id = node_event.event_id

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

                    # Analyze execution flow
                    execution_flow = _analyze_execution_flow(execution_sequence)

                    # Add additional metadata to the data dict
                    end_event.data.update({
                        "status": end_event_data["status"],
                        "is_subgraph": is_nested_subgraph,
                        "depth": current_depth,
                        "execution_flow": execution_flow,
                        "execution_sequence": [
                            {
                                "node_name": item["node_name"],
                                "sequence_index": item["sequence_index"],
                                "duration_ms": (item["end_time"] - item["start_time"]) * 1000.0
                            }
                            for item in execution_sequence
                        ],
                        "graph_structure": graph_structure,
                    })

                    if error:
                        end_event.data["error"] = end_event_data["error"]

                    # Set parent relationship - connect to last executed node to show flow
                    # For nested subgraphs, still use the parent_event_id
                    if is_nested_subgraph and parent_event_id:
                        end_event.parent_event_id = parent_event_id
                    elif last_node_event_id:
                        end_event.parent_event_id = last_node_event_id
                    elif agent_start_event_id:
                        # Fallback to agent start if no nodes executed
                        end_event.parent_event_id = agent_start_event_id

                    # Set sequential flow relationship
                    if previous_event_id:
                        end_event.previous_event_id = previous_event_id

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
