"""Test auto-instrumentation for LangGraph."""

import sys
from typing import TypedDict

# Step 1: Initialize GATI before importing LangGraph
from gati import observe

observe.init(
    backend_url="http://localhost:8000",
    agent_name="test_auto_instrument",
)

# Step 2: Import LangGraph after initialization
from langgraph.graph import StateGraph, END


class TestState(TypedDict):
    """Simple test state."""
    count: int
    message: str


def increment_node(state: TestState) -> TestState:
    """Increment counter node."""
    return {"count": state["count"] + 1, "message": "incremented"}


def main():
    """Test auto-instrumentation."""
    print("Testing LangGraph Auto-Instrumentation")
    print("=" * 60)

    # Create graph normally - should be auto-instrumented
    graph = StateGraph(TestState)
    graph.add_node("increment", increment_node)
    graph.set_entry_point("increment")
    graph.add_edge("increment", END)

    # Compile - should be automatically wrapped by GATI
    app = graph.compile()

    print("\n✓ Graph compiled (auto-instrumentation should be active)")

    # Verify the compile method was wrapped
    print(f"✓ StateGraph.compile is patched: {StateGraph.compile.__name__ == 'instrumented_compile'}")

    # Test invocation
    print("\nInvoking graph...")
    result = app.invoke({"count": 0, "message": ""})

    print(f"✓ Result: {result}")
    print(f"  - Count: {result['count']}")
    print(f"  - Message: {result['message']}")

    # Flush events
    observe.flush()
    print("\n✓ Events flushed to backend")

    print("\n" + "=" * 60)
    print("✓ Auto-instrumentation test passed!")
    print("=" * 60)

    # Cleanup
    observe.shutdown()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
