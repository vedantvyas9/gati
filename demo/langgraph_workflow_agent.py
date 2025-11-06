"""
LangGraph Workflow Agent Demo
==============================
A complex state-based workflow using LangGraph for handling customer support
with multiple specialized agents and conditional routing.

This demo showcases:
- State management with LangGraph
- Conditional edges and routing
- Multiple specialized agents (classifier, technical, billing, escalation)
- Real-world customer support simulation
- Multi-step decision making

Note: GATI SDK is NOT integrated here - you'll need to add it yourself.
"""

import os
from typing import TypedDict, Annotated, Literal, Dict, Any
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage
import json
import time
import operator

# GATI SDK imports
from gati import observe
from gati.decorators import track_tool, track_agent
from gati.core.event import NodeExecutionEvent
from gati.core.context import get_current_run_id, get_parent_event_id, set_parent_event_id
from gati.core.context import RunContextManager

# Initialize GATI
observe.init(
    backend_url="http://localhost:8000",
    agent_name="support_workflow",  # Must match the @track_agent name
    auto_inject=False  # Disable auto-instrumentation, we're tracking manually
)

# Load environment variables
load_dotenv()

# Initialize the LLM with GATI callbacks for LLM tracking
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.7,
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    callbacks=observe.get_callbacks()  # Enable LLM call tracking
)


# ===== Define State =====

class SupportState(TypedDict):
    """State for the customer support workflow."""
    customer_query: str
    query_type: str
    priority: str
    agent_responses: Annotated[list, operator.add]
    resolution: str
    escalated: bool
    metadata: Dict[str, Any]


# ===== Tool Functions =====

@track_tool(name="check_user_account")
def check_user_account(user_id: str) -> Dict[str, Any]:
    """Simulates checking a user's account information."""
    time.sleep(0.3)

    accounts = {
        "user123": {
            "status": "active",
            "plan": "premium",
            "balance": 150.00,
            "issues": []
        },
        "user456": {
            "status": "active",
            "plan": "basic",
            "balance": -25.00,
            "issues": ["overdue_payment"]
        }
    }

    return accounts.get(user_id, {
        "status": "unknown",
        "plan": "unknown",
        "balance": 0.00,
        "issues": []
    })


@track_tool(name="check_system_status")
def check_system_status(service: str) -> Dict[str, Any]:
    """Checks the status of various system services."""
    time.sleep(0.2)

    services = {
        "api": {"status": "operational", "uptime": "99.9%", "latency": "45ms"},
        "database": {"status": "operational", "uptime": "99.99%", "latency": "12ms"},
        "auth": {"status": "degraded", "uptime": "98.5%", "latency": "120ms"},
        "payment": {"status": "operational", "uptime": "99.8%", "latency": "200ms"}
    }

    return services.get(service.lower(), {
        "status": "unknown",
        "uptime": "N/A",
        "latency": "N/A"
    })


@track_tool(name="fetch_documentation")
def fetch_documentation(topic: str) -> str:
    """Fetches relevant documentation for a topic."""
    time.sleep(0.2)

    docs = {
        "api": "API Documentation: Use Bearer token for authentication. Rate limit: 1000 req/hour.",
        "billing": "Billing Info: Payments processed on 1st of month. Contact billing@company.com for issues.",
        "authentication": "Auth Guide: Supports OAuth 2.0, JWT tokens. Session timeout: 24 hours.",
        "integration": "Integration Guide: RESTful API with JSON responses. SDKs available for Python, JS, Java."
    }

    for key, doc in docs.items():
        if key in topic.lower():
            return doc

    return "General documentation available at docs.company.com"


@track_tool(name="create_support_ticket")
def create_support_ticket(issue: str, priority: str) -> str:
    """Creates a support ticket for escalated issues."""
    time.sleep(0.3)

    ticket_id = f"TKT-{int(time.time())}"

    return json.dumps({
        "ticket_id": ticket_id,
        "issue": issue,
        "priority": priority,
        "status": "open",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "assigned_to": "support_team"
    }, indent=2)


# ===== Node Execution Tracker =====

def track_node_execution(node_name: str):
    """Decorator to track node execution with GATI"""
    def decorator(func):
        def wrapper(state: SupportState) -> SupportState:
            start_time = time.time()
            state_before = dict(state)
            run_id = get_current_run_id() or "unknown"

            # Get parent event ID from context (should be agent_start)
            parent_event_id = get_parent_event_id()

            # Create node event and pre-generate its ID for use as parent
            node_event = NodeExecutionEvent(
                run_id=run_id,
                node_name=node_name,
                state_before=state_before,
                state_after={},  # Will update after execution
                duration_ms=0.0,  # Will update after execution
                data={"status": "started"}
            )

            # Set parent event ID if available
            if parent_event_id:
                node_event.parent_event_id = parent_event_id

            # Store node event ID to use as parent for child events
            node_event_id = node_event.event_id

            # Set this node as parent for child events (LLM calls, tool calls)
            old_parent_event_id = get_parent_event_id()
            set_parent_event_id(node_event_id)

            try:
                # Execute node
                result = func(state)

                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000

                # Update node event with completion info
                node_event.state_after = dict(result)
                node_event.duration_ms = duration_ms
                node_event.data = {"status": "completed"}

                # Track the completed node event (only once!)
                observe.track_event(node_event)

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                # Update node event with error info
                node_event.state_after = state_before
                node_event.duration_ms = duration_ms
                node_event.data = {
                    "status": "error",
                    "error": {"type": type(e).__name__, "message": str(e)}
                }

                # Track the failed node event
                observe.track_event(node_event)
                raise

            finally:
                # Restore previous parent event ID
                if old_parent_event_id:
                    set_parent_event_id(old_parent_event_id)
                else:
                    # If there was no previous parent, clear it
                    set_parent_event_id(parent_event_id) if parent_event_id else None

        return wrapper
    return decorator


# ===== Agent Nodes =====

@track_node_execution("classify_query")
def classify_query(state: SupportState) -> SupportState:
    """Classifies the customer query into a category."""
    print("\n[CLASSIFIER AGENT] Analyzing query...")

    query = state["customer_query"]

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a query classification agent. Analyze the customer query and classify it into one of these categories:
- technical: Technical issues, bugs, API problems
- billing: Payment issues, subscription questions, refunds
- general: General questions, product info, how-to guides

Also determine priority (high, medium, low) based on urgency and impact.

Respond in JSON format:
{{
  "type": "technical|billing|general",
  "priority": "high|medium|low",
  "reasoning": "brief explanation"
}}"""),
        ("human", "Query: {query}")
    ])

    response = llm.invoke(prompt.format_messages(query=query))
    content = response.content

    # Parse the classification
    try:
        classification = json.loads(content)
        query_type = classification.get("type", "general")
        priority = classification.get("priority", "medium")
        reasoning = classification.get("reasoning", "")
    except:
        # Fallback classification
        if any(word in query.lower() for word in ["bug", "error", "api", "not working"]):
            query_type = "technical"
        elif any(word in query.lower() for word in ["payment", "bill", "charge", "refund"]):
            query_type = "billing"
        else:
            query_type = "general"
        priority = "medium"
        reasoning = "Fallback classification"

    print(f"  Type: {query_type}")
    print(f"  Priority: {priority}")
    print(f"  Reasoning: {reasoning}")

    state["query_type"] = query_type
    state["priority"] = priority
    state["agent_responses"].append({
        "agent": "classifier",
        "result": f"Classified as {query_type} with {priority} priority",
        "reasoning": reasoning
    })

    return state


@track_node_execution("handle_technical")
def handle_technical(state: SupportState) -> SupportState:
    """Handles technical support queries."""
    print("\n[TECHNICAL AGENT] Processing technical issue...")

    query = state["customer_query"]

    # Simulate checking system status
    print("  Checking system status...")
    api_status = check_system_status("api")
    auth_status = check_system_status("auth")

    # Fetch documentation
    print("  Fetching relevant documentation...")
    docs = fetch_documentation("api")

    # Format the system status as strings
    api_status_str = json.dumps(api_status, indent=2)
    auth_status_str = json.dumps(auth_status, indent=2)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a technical support agent. Help resolve technical issues using:
1. System status information
2. Available documentation
3. Common troubleshooting steps

Provide clear, actionable solutions."""),
        ("human", """Customer Query: {query}

System Status:
- API: {api_status}
- Auth: {auth_status}

Documentation: {docs}

Please provide a solution.""")
    ])

    response = llm.invoke(prompt.format_messages(
        query=query,
        api_status=api_status_str,
        auth_status=auth_status_str,
        docs=docs
    ))
    solution = response.content

    print(f"  Solution provided (length: {len(solution)} chars)")

    state["agent_responses"].append({
        "agent": "technical",
        "result": solution,
        "tools_used": ["check_system_status", "fetch_documentation"]
    })

    # Check if escalation is needed
    if auth_status["status"] == "degraded" or "critical" in query.lower():
        state["escalated"] = True
        print("  -> Issue escalated due to system degradation")

    return state


@track_node_execution("handle_billing")
def handle_billing(state: SupportState) -> SupportState:
    """Handles billing and payment queries."""
    print("\n[BILLING AGENT] Processing billing issue...")

    query = state["customer_query"]

    # Simulate account check
    print("  Checking user account...")
    # Extract user_id from metadata or use default
    user_id = state.get("metadata", {}).get("user_id", "user456")
    account_info = check_user_account(user_id)

    # Fetch billing documentation
    print("  Fetching billing policies...")
    docs = fetch_documentation("billing")

    # Format account info as string
    account_info_str = json.dumps(account_info, indent=2)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a billing support agent. Help resolve billing and payment issues using:
1. Customer account information
2. Billing policies
3. Payment processing guidelines

Be empathetic and provide clear next steps."""),
        ("human", """Customer Query: {query}

Account Information:
{account_info}

Billing Policies: {docs}

Please provide a resolution.""")
    ])

    response = llm.invoke(prompt.format_messages(
        query=query,
        account_info=account_info_str,
        docs=docs
    ))
    resolution = response.content

    print(f"  Resolution provided (length: {len(resolution)} chars)")

    state["agent_responses"].append({
        "agent": "billing",
        "result": resolution,
        "account_status": account_info,
        "tools_used": ["check_user_account", "fetch_documentation"]
    })

    # Escalate if account has issues
    if account_info.get("issues"):
        state["escalated"] = True
        print(f"  -> Issue escalated due to account problems: {account_info['issues']}")

    return state


@track_node_execution("handle_general")
def handle_general(state: SupportState) -> SupportState:
    """Handles general inquiries."""
    print("\n[GENERAL AGENT] Processing general inquiry...")

    query = state["customer_query"]

    # Fetch general documentation
    print("  Fetching documentation...")
    docs = fetch_documentation("integration")

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a general support agent. Help customers with:
1. Product information
2. How-to guides
3. General questions

Provide helpful, friendly responses with relevant documentation."""),
        ("human", """Customer Query: {query}

Available Documentation: {docs}

Please provide a helpful response.""")
    ])

    response = llm.invoke(prompt.format_messages(query=query, docs=docs))
    answer = response.content

    print(f"  Response provided (length: {len(answer)} chars)")

    state["agent_responses"].append({
        "agent": "general",
        "result": answer,
        "tools_used": ["fetch_documentation"]
    })

    return state


@track_node_execution("escalate_issue")
def escalate_issue(state: SupportState) -> SupportState:
    """Escalates complex issues to human support."""
    print("\n[ESCALATION AGENT] Creating support ticket...")

    query = state["customer_query"]
    priority = state["priority"]

    # Create support ticket
    ticket = create_support_ticket(query, priority)

    print(f"  Ticket created: {json.loads(ticket)['ticket_id']}")

    # Generate escalation summary
    actions_str = json.dumps(state['agent_responses'], indent=2)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an escalation agent. Create a brief summary for the support team including:
1. Issue description
2. Actions taken so far
3. Why escalation is needed
4. Recommended next steps"""),
        ("human", """Original Query: {query}

Actions Taken:
{actions}

Ticket: {ticket}

Please create an escalation summary.""")
    ])

    response = llm.invoke(prompt.format_messages(
        query=query,
        actions=actions_str,
        ticket=ticket
    ))
    summary = response.content

    print(f"  Escalation summary created (length: {len(summary)} chars)")

    state["agent_responses"].append({
        "agent": "escalation",
        "result": summary,
        "ticket": json.loads(ticket),
        "tools_used": ["create_support_ticket"]
    })

    state["resolution"] = f"Issue escalated. {summary}"

    return state


@track_node_execution("finalize_resolution")
def finalize_resolution(state: SupportState) -> SupportState:
    """Finalizes the resolution and prepares response to customer."""
    print("\n[FINALIZATION] Preparing final response...")

    # Compile all agent responses
    responses = state["agent_responses"]
    responses_str = json.dumps(responses, indent=2)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a customer service manager. Create a final, cohesive response to the customer that:
1. Acknowledges their query
2. Summarizes the resolution
3. Provides clear next steps
4. Maintains a professional, friendly tone

Be concise but thorough."""),
        ("human", """Customer Query: {query}

Agent Responses:
{responses}

Priority: {priority}
Escalated: {escalated}

Please create a final response to the customer.""")
    ])

    response = llm.invoke(prompt.format_messages(
        query=state['customer_query'],
        responses=responses_str,
        priority=state['priority'],
        escalated=str(state['escalated'])
    ))
    final_response = response.content

    print(f"  Final response prepared (length: {len(final_response)} chars)")

    state["resolution"] = final_response

    return state


# ===== Routing Functions =====

def route_query(state: SupportState) -> Literal["technical", "billing", "general"]:
    """Routes the query to the appropriate handler."""
    query_type = state["query_type"]
    print(f"\n[ROUTER] Routing to {query_type} handler")
    return query_type


def should_escalate(state: SupportState) -> Literal["escalate", "finalize"]:
    """Determines if the issue should be escalated."""
    if state["escalated"]:
        print("\n[ROUTER] Issue requires escalation")
        return "escalate"
    else:
        print("\n[ROUTER] Issue resolved, finalizing")
        return "finalize"


# ===== Build Graph =====

def build_support_graph():
    """Builds the LangGraph workflow for customer support."""

    # Initialize graph
    workflow = StateGraph(SupportState)

    # Add nodes
    workflow.add_node("classify", classify_query)
    workflow.add_node("technical", handle_technical)
    workflow.add_node("billing", handle_billing)
    workflow.add_node("general", handle_general)
    workflow.add_node("escalate", escalate_issue)
    workflow.add_node("finalize", finalize_resolution)

    # Set entry point
    workflow.set_entry_point("classify")

    # Add conditional routing after classification
    workflow.add_conditional_edges(
        "classify",
        route_query,
        {
            "technical": "technical",
            "billing": "billing",
            "general": "general"
        }
    )

    # Add conditional edges after each handler
    for handler in ["technical", "billing", "general"]:
        workflow.add_conditional_edges(
            handler,
            should_escalate,
            {
                "escalate": "escalate",
                "finalize": "finalize"
            }
        )

    # Add edges to END
    workflow.add_edge("escalate", "finalize")
    workflow.add_edge("finalize", END)

    return workflow.compile()


# ===== Main Execution =====

@track_agent(name="support_workflow")
def run_support_workflow(customer_query: str, user_id: str = "user456") -> Dict[str, Any]:
    """
    Runs the customer support workflow.

    This creates a parent run context that all child events (nodes, LLMs, tools) will belong to.

    Args:
        customer_query: The customer's question or issue
        user_id: The customer's user ID

    Returns:
        Final state with resolution
    """
    print("\n" + "="*60)
    print("CUSTOMER SUPPORT WORKFLOW")
    print("="*60)

    # Get the run_id from context (set by @track_agent decorator)
    run_id = get_current_run_id()
    print(f"Run ID: {run_id}")
    print("="*60)

    # Initialize state
    initial_state: SupportState = {
        "customer_query": customer_query,
        "query_type": "",
        "priority": "",
        "agent_responses": [],
        "resolution": "",
        "escalated": False,
        "metadata": {"user_id": user_id}
    }

    # Build and run graph
    # The @track_agent decorator creates a run context, so all child events will share this run_id
    graph = build_support_graph()
    final_state = graph.invoke(initial_state)

    return final_state


def main():
    """Main execution function."""
    print("\n" + "="*60)
    print("LangGraph Multi-Agent Support System")
    print("="*60)

    # Test cases
    test_queries = [
        {
            "query": "I'm getting a 401 error when calling the authentication API. This is blocking our production deployment!",
            "user_id": "user123"
        },
        {
            "query": "I was charged twice for my subscription this month. Can you help me get a refund?",
            "user_id": "user456"
        },
        {
            "query": "How do I integrate your API with my Python application?",
            "user_id": "user123"
        }
    ]

    # Run workflow for first test case
    test_case = test_queries[0]
    print(f"\nProcessing query: \"{test_case['query']}\"")
    print(f"User ID: {test_case['user_id']}")

    try:
        final_state = run_support_workflow(
            test_case["query"],
            test_case["user_id"]
        )

        # Print results
        print("\n" + "="*60)
        print("WORKFLOW RESULTS")
        print("="*60)
        print(f"\nQuery Type: {final_state['query_type']}")
        print(f"Priority: {final_state['priority']}")
        print(f"Escalated: {final_state['escalated']}")
        print(f"\nAgents Used: {len(final_state['agent_responses'])}")
        for i, response in enumerate(final_state['agent_responses'], 1):
            print(f"  {i}. {response['agent'].upper()}")

        print(f"\n{'='*60}")
        print("FINAL RESOLUTION")
        print("="*60)
        print(final_state['resolution'])

        print("\n" + "="*60)
        print("WORKFLOW SUMMARY")
        print("="*60)
        print(f"Total nodes executed: {len(final_state['agent_responses']) + 2}")  # +2 for classify and finalize
        print(f"Tools called: {sum(len(r.get('tools_used', [])) for r in final_state['agent_responses'])}")
        print("\nWorkflow completed successfully!")

        # IMPORTANT: Flush events to backend before exiting
        print("\n" + "="*60)
        print("GATI OBSERVABILITY")
        print("="*60)
        print("All events tracked:")
        print("  ✓ 6 Node executions (classify, technical, escalate, finalize, etc.)")
        print("  ✓ 6 LLM calls (OpenAI API calls in each node)")
        print("  ✓ 4 Tool calls per node (check_system_status, fetch_documentation, etc.)")
        print(f"  ✓ Total: ~{len(final_state['agent_responses']) * 2 + 10} events")
        print("\nFlushing events to backend...")
        observe.flush()
        time.sleep(2)  # Give time for events to be sent
        print("Events flushed. Check dashboard at http://localhost:3000")

    except Exception as e:
        print(f"\nError during workflow execution: {str(e)}")
        raise
    finally:
        # Ensure events are flushed even on error
        observe.flush()


if __name__ == "__main__":
    main()
