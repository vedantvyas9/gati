"""Test script for LangGraph instrumentation.

This script demonstrates and tests the GATI LangGraph wrapper with a sample
graph that includes multiple nodes, state transitions, and error handling.
"""

import asyncio
from typing import TypedDict, Annotated
from typing_extensions import TypedDict as ExtTypedDict

# Initialize GATI first
from gati import observe

observe.init(
    backend_url="http://localhost:8000",
    agent_name="test_langgraph_agent",
)

# Import LangGraph after GATI initialization
try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    print("LangGraph not available. Install with: pip install langgraph")
    LANGGRAPH_AVAILABLE = False
    exit(1)


# Define a simple state schema
class AgentState(TypedDict):
    """State schema for the test agent."""
    input: str
    step_count: int
    output: str
    history: list


# Define node functions
def step1_process_input(state: AgentState) -> AgentState:
    """First processing step."""
    print(f"Step 1: Processing input '{state['input']}'")

    return {
        **state,
        "step_count": state.get("step_count", 0) + 1,
        "output": f"Processed: {state['input']}",
        "history": state.get("history", []) + ["step1"],
    }


def step2_transform(state: AgentState) -> AgentState:
    """Second processing step."""
    print(f"Step 2: Transforming '{state['output']}'")

    return {
        **state,
        "step_count": state.get("step_count", 0) + 1,
        "output": state["output"].upper(),
        "history": state.get("history", []) + ["step2"],
    }


def step3_finalize(state: AgentState) -> AgentState:
    """Final processing step."""
    print(f"Step 3: Finalizing '{state['output']}'")

    return {
        **state,
        "step_count": state.get("step_count", 0) + 1,
        "output": f"Final: {state['output']}",
        "history": state.get("history", []) + ["step3"],
    }


def step_with_error(state: AgentState) -> AgentState:
    """Step that raises an error for testing error handling."""
    print("Step with error: This will fail!")
    raise ValueError("Intentional error for testing")


# Async node function for testing async support
async def async_step(state: AgentState) -> AgentState:
    """Async processing step."""
    print("Async step: Processing asynchronously")
    await asyncio.sleep(0.1)  # Simulate async work

    return {
        **state,
        "step_count": state.get("step_count", 0) + 1,
        "output": f"Async: {state['output']}",
        "history": state.get("history", []) + ["async_step"],
    }


def create_test_graph() -> StateGraph:
    """Create a test graph with multiple nodes."""
    # Create the graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("step1", step1_process_input)
    workflow.add_node("step2", step2_transform)
    workflow.add_node("step3", step3_finalize)

    # Define edges
    workflow.set_entry_point("step1")
    workflow.add_edge("step1", "step2")
    workflow.add_edge("step2", "step3")
    workflow.add_edge("step3", END)

    return workflow


def create_async_test_graph() -> StateGraph:
    """Create a test graph with async nodes."""
    workflow = StateGraph(AgentState)

    workflow.add_node("step1", step1_process_input)
    workflow.add_node("async_step", async_step)
    workflow.add_node("step3", step3_finalize)

    workflow.set_entry_point("step1")
    workflow.add_edge("step1", "async_step")
    workflow.add_edge("async_step", "step3")
    workflow.add_edge("step3", END)

    return workflow


def create_error_test_graph() -> StateGraph:
    """Create a test graph that includes an error node."""
    workflow = StateGraph(AgentState)

    workflow.add_node("step1", step1_process_input)
    workflow.add_node("error_step", step_with_error)
    workflow.add_node("step3", step3_finalize)

    workflow.set_entry_point("step1")
    workflow.add_edge("step1", "error_step")
    workflow.add_edge("error_step", "step3")
    workflow.add_edge("step3", END)

    return workflow


def test_basic_invoke():
    """Test basic graph invocation with tracking."""
    print("\n=== Test 1: Basic Invoke ===")

    # Create the graph (auto-instrumentation happens on compile)
    graph = create_test_graph()
    app = graph.compile()  # Automatically instrumented!

    # Test input
    initial_state = {
        "input": "Hello, World!",
        "step_count": 0,
        "output": "",
        "history": [],
    }

    # Run the graph
    result = app.invoke(initial_state)

    print(f"\nResult: {result}")
    print(f"Step count: {result['step_count']}")
    print(f"History: {result['history']}")
    print(f"Final output: {result['output']}")

    assert result["step_count"] == 3, "Should have run 3 steps"
    assert "step1" in result["history"], "Should have step1 in history"
    assert "step2" in result["history"], "Should have step2 in history"
    assert "step3" in result["history"], "Should have step3 in history"

    print("✓ Test passed!")


def test_stream():
    """Test graph streaming with tracking."""
    print("\n=== Test 2: Stream ===")

    graph = create_test_graph()
    app = graph.compile()  # Automatically instrumented!

    initial_state = {
        "input": "Stream test",
        "step_count": 0,
        "output": "",
        "history": [],
    }

    print("\nStreaming results:")
    chunk_count = 0
    final_result = None

    for chunk in app.stream(initial_state):
        chunk_count += 1
        print(f"Chunk {chunk_count}: {chunk}")
        final_result = chunk

    print(f"\nTotal chunks: {chunk_count}")
    if final_result:
        print(f"Final output: {final_result}")

    print("✓ Test passed!")


async def test_async_invoke():
    """Test async graph invocation with tracking."""
    print("\n=== Test 3: Async Invoke ===")

    graph = create_async_test_graph()
    app = graph.compile()  # Automatically instrumented!

    initial_state = {
        "input": "Async test",
        "step_count": 0,
        "output": "",
        "history": [],
    }

    # Run async
    result = await app.ainvoke(initial_state)

    print(f"\nAsync result: {result}")
    print(f"Step count: {result['step_count']}")
    print(f"History: {result['history']}")

    assert "async_step" in result["history"], "Should have async_step in history"

    print("✓ Test passed!")


async def test_async_stream():
    """Test async graph streaming with tracking."""
    print("\n=== Test 4: Async Stream ===")

    graph = create_async_test_graph()
    app = graph.compile()  # Automatically instrumented!

    initial_state = {
        "input": "Async stream test",
        "step_count": 0,
        "output": "",
        "history": [],
    }

    print("\nAsync streaming results:")
    chunk_count = 0
    final_result = None

    async for chunk in app.astream(initial_state):
        chunk_count += 1
        print(f"Async chunk {chunk_count}: {chunk}")
        final_result = chunk

    print(f"\nTotal async chunks: {chunk_count}")
    if final_result:
        print(f"Final async output: {final_result}")

    print("✓ Test passed!")


def test_error_handling():
    """Test error handling in graph execution."""
    print("\n=== Test 5: Error Handling ===")

    graph = create_error_test_graph()
    app = graph.compile()  # Automatically instrumented!

    initial_state = {
        "input": "Error test",
        "step_count": 0,
        "output": "",
        "history": [],
    }

    try:
        result = app.invoke(initial_state)
        print("ERROR: Should have raised an exception!")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        print(f"\n✓ Caught expected error: {e}")
        print("✓ Error handling test passed!")


def test_state_diff():
    """Test state diff calculation."""
    print("\n=== Test 6: State Diff Calculation ===")

    from gati.instrumentation.langgraph.auto_inject import _calculate_state_diff

    # Test with dicts
    state_before = {
        "input": "test",
        "count": 0,
        "output": "",
    }

    state_after = {
        "input": "test",
        "count": 1,
        "output": "processed",
    }

    diff = _calculate_state_diff(state_before, state_after)

    print(f"\nState diff: {diff}")

    assert "count" in diff, "Should detect count change"
    assert "output" in diff, "Should detect output change"
    assert "input" not in diff, "Should not include unchanged fields"

    print("✓ Test passed!")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("GATI LangGraph Instrumentation Test Suite")
    print("=" * 60)

    try:
        # Sync tests
        test_basic_invoke()
        test_stream()
        test_state_diff()
        test_error_handling()

        # Async tests
        print("\n--- Running Async Tests ---")
        asyncio.run(test_async_invoke())
        asyncio.run(test_async_stream())

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)

        # Flush events to backend
        print("\nFlushing events to backend...")
        observe.flush()

        # Wait a bit for flush to complete
        import time
        time.sleep(2)

        print("✓ Events flushed!")

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        # Shutdown GATI
        print("\nShutting down GATI...")
        observe.shutdown()
        print("✓ Shutdown complete!")


if __name__ == "__main__":
    if not LANGGRAPH_AVAILABLE:
        print("LangGraph not available. Install with: pip install langgraph")
        exit(1)

    run_all_tests()
