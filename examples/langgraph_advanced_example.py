"""Advanced LangGraph instrumentation example with LLM calls and nested subgraphs.

This example demonstrates comprehensive tracking of:
- LangGraph graphs with multiple nodes
- LLM calls within nodes (via LangChain instrumentation)
- Tool calls within nodes
- Nested subgraphs
- Rich node metadata (function names, types, durations, errors)
- Complete parent-child event relationships
"""

from typing import TypedDict, Annotated, List
import operator

# Step 1: Initialize GATI (enables auto-instrumentation)
from gati import observe

observe.init(
    backend_url="http://localhost:8000",
    agent_name="advanced_langgraph_agent",
)

# Step 2: Import LangGraph and LangChain
from langgraph.graph import StateGraph, END

# Import LangChain for LLM calls (mock for testing without API key)
try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    print("Warning: LangChain OpenAI not available. Using mock LLM.")


# Step 3: Define state schema
class ResearchState(TypedDict):
    """State for research agent."""
    query: str
    research_notes: Annotated[List[str], operator.add]
    analysis_result: str
    final_answer: str


# Step 4: Define node functions (some with LLM calls)
def research_node(state: ResearchState) -> ResearchState:
    """Research node that gathers information (simulated LLM call)."""
    print(f"🔍 Researching: {state['query']}")

    # Simulate LLM call if available
    if LLM_AVAILABLE:
        try:
            llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
            messages = [
                SystemMessage(content="You are a helpful research assistant."),
                HumanMessage(content=f"Provide brief research notes on: {state['query']}")
            ]
            # This LLM call will be automatically tracked by GATI
            response = llm.invoke(messages)
            research_note = response.content
        except Exception as e:
            print(f"Mock LLM call (API key not set): {e}")
            research_note = f"Research note: Information about {state['query']}"
    else:
        research_note = f"Research note: Information about {state['query']}"

    return {
        **state,
        "research_notes": [research_note],
    }


def analyze_node(state: ResearchState) -> ResearchState:
    """Analyze node that processes research notes."""
    print("🔬 Analyzing research notes...")

    # Combine research notes
    all_notes = "\n".join(state.get("research_notes", []))

    # Simulate analysis
    analysis = f"Analysis: Based on {len(state.get('research_notes', []))} notes"

    return {
        **state,
        "analysis_result": analysis,
    }


def synthesize_node(state: ResearchState) -> ResearchState:
    """Synthesize final answer from analysis."""
    print("✨ Synthesizing final answer...")

    # Create final answer
    final_answer = f"Answer to '{state['query']}': {state.get('analysis_result', 'N/A')}"

    return {
        **state,
        "final_answer": final_answer,
    }


def error_prone_node(state: ResearchState) -> ResearchState:
    """Node that may fail (for testing error tracking)."""
    print("⚠️ Running error-prone node...")

    # Intentionally cause an error sometimes (commented out for normal execution)
    # if "error" in state.get("query", "").lower():
    #     raise ValueError("Intentional error for testing!")

    return state


# Step 5: Create the graph
def create_research_graph():
    """Create a research graph with multiple nodes."""
    workflow = StateGraph(ResearchState)

    # Add nodes
    workflow.add_node("research", research_node)
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("synthesize", synthesize_node)

    # Set entry point
    workflow.set_entry_point("research")

    # Add edges (linear flow)
    workflow.add_edge("research", "analyze")
    workflow.add_edge("analyze", "synthesize")
    workflow.add_edge("synthesize", END)

    # Compile with automatic GATI instrumentation
    return workflow.compile()


# Step 6: Create a nested subgraph example
def create_subgraph():
    """Create a simple subgraph for nested testing."""
    subworkflow = StateGraph(ResearchState)

    # Simple node
    def subnode(state: ResearchState) -> ResearchState:
        print("  🔹 Subgraph node executing...")
        return {
            **state,
            "research_notes": ["Subgraph processed data"],
        }

    subworkflow.add_node("subnode", subnode)
    subworkflow.set_entry_point("subnode")
    subworkflow.add_edge("subnode", END)

    return subworkflow.compile()


def create_nested_graph():
    """Create a graph with nested subgraph calls."""
    workflow = StateGraph(ResearchState)

    # Create subgraph
    subgraph = create_subgraph()

    # Main node that calls subgraph
    def main_node(state: ResearchState) -> ResearchState:
        print("📊 Main node calling subgraph...")
        # Call subgraph (will be tracked as nested)
        result = subgraph.invoke(state)
        return result

    workflow.add_node("main", main_node)
    workflow.set_entry_point("main")
    workflow.add_edge("main", END)

    return workflow.compile()


# Example usage
def main():
    """Run the advanced example."""
    print("=" * 70)
    print("GATI Advanced LangGraph Instrumentation Example")
    print("=" * 70)

    # Test 1: Basic graph with multiple nodes
    print("\n--- Test 1: Multi-node graph ---")
    app = create_research_graph()

    result1 = app.invoke({
        "query": "What is quantum computing?",
        "research_notes": [],
        "analysis_result": "",
        "final_answer": "",
    })
    print(f"\n✅ Result: {result1['final_answer']}")

    # Test 2: Nested subgraph
    print("\n--- Test 2: Nested subgraph ---")
    nested_app = create_nested_graph()

    result2 = nested_app.invoke({
        "query": "Test nested execution",
        "research_notes": [],
        "analysis_result": "",
        "final_answer": "",
    })
    print(f"\n✅ Nested result processed")

    # Test 3: Stream execution
    print("\n--- Test 3: Stream execution ---")
    app2 = create_research_graph()

    print("Streaming graph execution...")
    for chunk in app2.stream({
        "query": "Machine learning basics",
        "research_notes": [],
        "analysis_result": "",
        "final_answer": "",
    }):
        node_name = list(chunk.keys())[0] if chunk else "unknown"
        print(f"  → Node '{node_name}' completed")

    # Flush events to backend
    print("\n--- Flushing events to backend ---")
    observe.flush()

    print("\n" + "=" * 70)
    print("✓ Advanced example completed!")
    print("=" * 70)
    print("\nCheck your GATI dashboard to see:")
    print("  • Graph-level tracking (AgentStart/End)")
    print("  • Node-level tracking with metadata:")
    print("    - Function names (research_node, analyze_node, etc.)")
    print("    - Node types (custom, llm, tool, subgraph)")
    print("    - Durations for each node")
    print("    - State diffs showing what each node changed")
    print("  • LLM calls within nodes (if API key configured)")
    print("  • Nested subgraph tracking with parent relationships")
    print("  • Complete event hierarchy with run_id and parent_event_id")
    print("\nAll tracking happened automatically!")

    # Shutdown
    observe.shutdown()


if __name__ == "__main__":
    main()
