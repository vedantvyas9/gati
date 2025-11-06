import os
import time
from typing import Annotated, TypedDict
from dotenv import load_dotenv

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from gati import observe 
observe.init(agent_name = "travel agent", backend_url = "http://localhost:8000")
# -----------------
# 1. INITIAL SETUP & STATE DEFINITION
# -----------------

# Load environment variables from .env file
load_dotenv()

# Check for API Key
if not os.getenv("OPENAI_API_KEY"):
    print("FATAL ERROR: OPENAI_API_KEY not found. Please populate the .env file.")
    exit()

# Define the State Schema for the LangGraph
# This state is passed between all nodes and dictates the context.
class AgentState(TypedDict):
    """Represents the state of our graph/workflow."""
    # The primary message/task from the user
    request: str
    # Raw data gathered from the research tool
    research_result: str
    # Final, formatted output for the user
    final_plan: str
    # A counter to prevent infinite loops during tool calls (not strictly used here, but good practice)
    tool_calls_count: int


# Initialize the LLM
# Ensure you use a model that supports tool calling for complex agent flows (like gpt-4o or gpt-4-turbo)
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

print(f"--- System Initialized (Model: {llm.model_name}) ---")

# -----------------
# 2. TOOL DEFINITION (for Researcher Agent)
# -----------------

@tool
def simulated_research(query: Annotated[str, "The destination or topic to research."]) -> str:
    """
    A simulated web search tool to find key information about a travel destination.
    In a real application, this would use Google Search, Tavily, or another API.
    """
    print(f"\n[TOOL CALLED: simulated_research('{query}')]")
    time.sleep(1) # Simulate API latency

    if "Paris" in query:
        return (
            "Paris, France is known as the 'City of Love.' Key attractions include "
            "the Eiffel Tower, Louvre Museum (home to the Mona Lisa), and Notre Dame Cathedral. "
            "Weather in October is typically 10°C to 18°C (50°F to 64°F), often rainy. "
            "Cost is high. Major activities are art, history, and fine dining."
        )
    elif "Tokyo" in query:
        return (
            "Tokyo, Japan is a dense, high-tech metropolis. Attractions include "
            "Shibuya Crossing, Sensō-ji Temple, and the Imperial Palace. "
            "Weather in October is mild and pleasant, averaging 15°C to 22°C (59°F to 72°F). "
            "Cost is moderate to high. Major activities are food, shopping, and modern culture."
        )
    else:
        return f"No specific data found for '{query}'. Assuming a generic city known for good food and history."

# -----------------
# 3. LLM CHAIN (for Summarizer Agent)
# -----------------

# Define the LCEL chain for the summarization step
summarizer_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", 
         "You are the Final Travel Planner. Your job is to take raw research data and a user request "
         "and synthesize a concise, beautifully formatted travel summary (max 3 bullet points, max 100 words). "
         "ALWAYS structure the output cleanly. Do not use conversational filler."),
        ("user", 
         "User Request: {request}\n\n"
         "Raw Research Data:\n{research_result}\n\n"
         "Create the final summary.")
    ]
)

# This is the LLM Chain (LLM + Prompt + Output Parser)
summarizer_chain = summarizer_prompt | llm | StrOutputParser()

# -----------------
# 4. LANGGRAPH NODES (Sub-Agents)
# -----------------

# Node 1: Researcher Agent - Responsible for calling the tool
def research_agent_node(state: AgentState) -> AgentState:
    """
    Executes the research tool and updates the research_result in the state.
    """
    request = state["request"]
    print("\n[STEP 1: RESEARCHER AGENT] Executing tool...")
    
    # Simple logic to extract the location for the tool call
    # A real agent would use the LLM to decide tool inputs.
    query_parts = request.split()
    query = next((part for part in query_parts if part[0].isupper() and len(part) > 3), "a city")
    
    result = simulated_research.invoke({"query": query})
    
    # Update the state with the tool's result
    return {"research_result": result}

# Node 2: Summarizer Agent - Responsible for running the LLM chain (LCEL)
def summarizer_agent_node(state: AgentState) -> AgentState:
    """
    Executes the LLM Chain (LCEL) to summarize and format the research result.
    """
    print("\n[STEP 2: SUMMARIZER AGENT] Executing LLM Chain...")
    
    # Prepare input dictionary for the LCEL chain
    chain_input = {
        "request": state["request"],
        "research_result": state["research_result"]
    }
    
    # Invoke the chain
    final_plan_text = summarizer_chain.invoke(chain_input)
    
    # Update the state with the final plan
    return {"final_plan": final_plan_text}

# -----------------
# 5. GRAPH DEFINITION AND COMPILATION
# -----------------

# 5.1. Define the graph structure
builder = StateGraph(AgentState)

# Add the two sub-agent nodes
builder.add_node("research", research_agent_node)
builder.add_node("summarize", summarizer_agent_node)

# Set the entry point
builder.set_entry_point("research")

# Define edges (flow control)
# After research, always go to summarize
builder.add_edge("research", "summarize")

# After summarize, the task is finished
builder.add_edge("summarize", END)

# 5.2. Compile the graph
app = builder.compile()

# -----------------
# 6. EXECUTION
# -----------------

def run_travel_planner(task: str):
    """
    Invokes the compiled LangGraph agent.
    """
    print(f"\n=======================================================")
    print(f"| RUNNING AGENT FOR TASK: {task}")
    print(f"=======================================================")
    
    # Initial state with the user request
    initial_state = {
        "request": task, 
        "research_result": "", 
        "final_plan": "", 
        "tool_calls_count": 0
    }
    
    # Invoke the graph
    # We step through the graph and accumulate the final state
    final_state = app.invoke(initial_state)

    print("\n[STEP 3: FINAL OUTPUT]")
    print("-------------------------------------------------------")
    print(final_state["final_plan"])
    print("-------------------------------------------------------")
    print("\nFinal State Data:")
    print(f"  - Request: {final_state['request']}")
    print(f"  - Raw Research: {final_state['research_result'][:70]}...")

if __name__ == "__main__":
    # Example 1: Task triggering specific tool result
    run_travel_planner("I am planning a trip to Paris in October. I need a short summary of what to expect.")

    # Example 2: Task triggering a different specific tool result
    run_travel_planner("Please summarize a travel plan for Tokyo, Japan, focusing on food and temples.")

    # Example 3: Task for which there is no specific data
    run_travel_planner("Can you give me a travel overview for Buenos Aires next week?")

    # Flush all events to backend
    print("\n[Flushing events to backend...]")
    observe.flush()
    time.sleep(3)  # Give time for events to reach backend
    print("[Done]")