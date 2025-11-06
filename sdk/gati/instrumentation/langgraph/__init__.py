"""LangGraph instrumentation for GATI.

This package provides automatic instrumentation for LangGraph by monkey-patching
the StateGraph.compile() method to wrap all compiled graphs with tracking.

Usage:
    from gati import observe

    # Initialize - auto-instrumentation is enabled by default
    observe.init(backend_url="http://localhost:8000")

    # Use LangGraph normally - everything is tracked!
    from langgraph.graph import StateGraph

    graph = StateGraph(MyState)
    graph.add_node("node1", node1_func)
    app = graph.compile()  # ← Automatically instrumented!

    result = app.invoke({"input": "..."})  # ← All execution tracked!
"""

from gati.instrumentation.langgraph.auto_inject import instrument_langgraph

__all__ = [
    "instrument_langgraph",
]
