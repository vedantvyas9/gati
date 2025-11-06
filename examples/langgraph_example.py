"""Example: Using GATI with LangGraph for automatic tracking.

This example demonstrates how GATI automatically tracks LangGraph execution
with zero code changes - just initialize GATI and use LangGraph normally!
"""

from typing import TypedDict, Annotated, Literal
import operator

# Step 1: Initialize GATI (enables auto-instrumentation)
from gati import observe

observe.init(
    backend_url="http://localhost:8000",  # Your GATI backend URL
    agent_name="my_langgraph_agent",
)

# Step 2: Import LangGraph - use it normally, tracking is automatic!
from langgraph.graph import StateGraph, END


# Step 3: Define your state schema
class AgentState(TypedDict):
    """State schema for the agent."""
    messages: Annotated[list, operator.add]  # Messages accumulate
    next_step: str
    result: str


# Step 4: Define your node functions
def analyze_input(state: AgentState) -> AgentState:
    """Analyze the input and determine next step."""
    messages = state.get("messages", [])
    last_message = messages[-1] if messages else ""

    print(f"Analyzing input: {last_message}")

    # Simple logic to determine next step
    if "question" in last_message.lower():
        next_step = "answer_question"
    elif "task" in last_message.lower():
        next_step = "execute_task"
    else:
        next_step = "general_response"

    return {
        **state,
        "messages": [f"Analysis: Input type determined"],
        "next_step": next_step,
    }


def answer_question(state: AgentState) -> AgentState:
    """Answer a question."""
    print("Answering question...")

    return {
        **state,
        "messages": [f"Answer: Here is the answer to your question"],
        "result": "question_answered",
    }


def execute_task(state: AgentState) -> AgentState:
    """Execute a task."""
    print("Executing task...")

    return {
        **state,
        "messages": [f"Task: Task completed successfully"],
        "result": "task_executed",
    }


def general_response(state: AgentState) -> AgentState:
    """Provide a general response."""
    print("Generating general response...")

    return {
        **state,
        "messages": [f"Response: General response generated"],
        "result": "general_response_sent",
    }


def route_next_step(state: AgentState) -> Literal["answer_question", "execute_task", "general_response"]:
    """Route to the next step based on analysis."""
    next_step = state.get("next_step", "general_response")
    return next_step  # type: ignore


# Step 5: Create your graph
def create_agent_graph():
    """Create and compile the agent graph - GATI tracks it automatically!"""

    # Create the graph normally
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("analyze", analyze_input)
    workflow.add_node("answer_question", answer_question)
    workflow.add_node("execute_task", execute_task)
    workflow.add_node("general_response", general_response)

    # Set entry point
    workflow.set_entry_point("analyze")

    # Add conditional edges
    workflow.add_conditional_edges(
        "analyze",
        route_next_step,
        {
            "answer_question": "answer_question",
            "execute_task": "execute_task",
            "general_response": "general_response",
        }
    )

    # All paths end after their respective nodes
    workflow.add_edge("answer_question", END)
    workflow.add_edge("execute_task", END)
    workflow.add_edge("general_response", END)

    # Step 6: Compile normally - GATI automatically wraps it for tracking!
    # No need for GatiStateGraphWrapper - auto-instrumentation handles it
    app = workflow.compile()

    return app


# Example usage
def main():
    """Run the example."""
    print("=" * 60)
    print("GATI LangGraph Example")
    print("=" * 60)

    # Create the instrumented graph
    app = create_agent_graph()

    # Test 1: Question
    print("\n--- Test 1: Question ---")
    result1 = app.invoke({
        "messages": ["I have a question about Python"],
        "next_step": "",
        "result": "",
    })
    print(f"Result: {result1['result']}")
    print(f"Messages: {result1['messages']}")

    # Test 2: Task
    print("\n--- Test 2: Task ---")
    result2 = app.invoke({
        "messages": ["I need help with a task"],
        "next_step": "",
        "result": "",
    })
    print(f"Result: {result2['result']}")
    print(f"Messages: {result2['messages']}")

    # Test 3: General
    print("\n--- Test 3: General ---")
    result3 = app.invoke({
        "messages": ["Hello there"],
        "next_step": "",
        "result": "",
    })
    print(f"Result: {result3['result']}")
    print(f"Messages: {result3['messages']}")

    # Flush events to backend
    print("\n--- Flushing events ---")
    observe.flush()

    print("\n" + "=" * 60)
    print("✓ Example completed!")
    print("=" * 60)
    print("\nCheck your GATI dashboard to see the tracked events:")
    print("- AgentStartEvent: Graph execution started")
    print("- NodeExecutionEvent: Each node execution with state diffs")
    print("- AgentEndEvent: Graph execution completed")
    print("\nNote: All tracking happened automatically - no manual wrapping needed!")

    # Shutdown
    observe.shutdown()


if __name__ == "__main__":
    main()
