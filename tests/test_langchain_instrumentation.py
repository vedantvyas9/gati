import os
from typing import List

import pytest
from dotenv import load_dotenv
from unittest.mock import patch

from gati.observe import observe
from gati.core.event import LLMCallEvent, ToolCallEvent, StepEvent, AgentStartEvent, AgentEndEvent
from gati.instrumentation.langchain import GatiLangChainCallback

# Load env and check for API key
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


@pytest.fixture(autouse=True)
def capture_backend(monkeypatch):
    """Initialize observe and capture events by patching EventClient.send_events."""
    captured: List[object] = []

    def capture_send_events(self, events):
        """Capture events instead of sending to backend."""
        captured.extend(events)

    # Patch BEFORE initializing observe so the patched method is used
    monkeypatch.setattr("gati.core.client.EventClient.send_events", capture_send_events)

    # Fresh init per test with small batch for immediate flush
    observe.init(backend_url="http://localhost:8000", batch_size=1, flush_interval=0.01)

    yield captured

    try:
        observe.flush()
    finally:
        observe.shutdown()


@pytest.mark.skipif(not OPENAI_API_KEY, reason="OPENAI_API_KEY not set")
def test_real_langchain_llm_call(capture_backend):
    from langchain_openai import ChatOpenAI

    captured = capture_backend

    # Explicitly attach GATI callback to the LLM (works across LC versions)
    callback = GatiLangChainCallback()

    llm = ChatOpenAI(model="gpt-3.5-turbo", callbacks=[callback])
    out = llm.invoke("Say hello in 5 words")

    observe.flush()

    # We expect LLM start + end events
    llm_events = [e for e in captured if isinstance(e, LLMCallEvent)]
    assert len(llm_events) >= 2, f"Expected at least 2 LLM events, got {len(llm_events)}: {llm_events}"
    start = next(e for e in llm_events if e.data.get("status") == "started")
    end = next(e for e in llm_events if e.data.get("status") == "completed")

    assert "Say hello in 5 words" in (start.prompt or "")
    assert isinstance(end.completion, str) and len(end.completion) > 0
    assert end.tokens_in >= 0 and end.tokens_out >= 0
    assert end.cost >= 0.0


@pytest.mark.skipif(not OPENAI_API_KEY, reason="OPENAI_API_KEY not set")
def test_real_langchain_agent_with_tool(capture_backend):
    from langchain_openai import ChatOpenAI
    from langchain.agents import create_tool_calling_agent, AgentExecutor
    from langchain.tools import tool
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

    captured = capture_backend

    # Explicitly attach GATI callback at LLM level
    callback = GatiLangChainCallback()

    @tool
    def multiply(a: int, b: int) -> int:
        """Multiply two integers and return the result."""
        return a * b

    tools = [multiply]
    llm = ChatOpenAI(model="gpt-3.5-turbo", callbacks=[callback])
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful math assistant."),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)
    # Also attach callbacks to executor to capture tool events
    executor = AgentExecutor(agent=agent, tools=tools, callbacks=[callback], verbose=False)

    result = executor.invoke({"input": "What is 25 * 4? Use the multiply tool."})

    observe.flush()

    # Assertions: we should capture LLM calls and chain/step events from the agent executor
    # Note: LangChain 0.2.x typically represents tool calls as StepEvents (chains),
    # not separate ToolCallEvents. We verify we're capturing both LLM and execution flow.
    llm_events = [e for e in captured if isinstance(e, LLMCallEvent)]
    step_events = [e for e in captured if isinstance(e, StepEvent)]
    tool_events = [e for e in captured if isinstance(e, ToolCallEvent)]

    assert len(llm_events) > 0, f"Expected LLM events, got: {[type(e).__name__ for e in captured]}"
    # Either we get tool events OR step events (which include tool invocations in LangChain 0.2.x)
    assert len(tool_events) > 0 or len(step_events) > 0, \
        f"Expected tool or step events, got: {[type(e).__name__ for e in captured]}"

    # Verify the agent executed with multiple LLM calls (thinking then response)
    assert len(llm_events) >= 2, "Expected at least 2 LLM calls (agent reasoning and response)"



