"""Tests for automatic callback injection feature."""

import os
from typing import List
from unittest.mock import patch

import pytest
from dotenv import load_dotenv

from gati.observe import observe
from gati.core.event import LLMCallEvent

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

    # Check if observe is already initialized (from previous tests)
    was_initialized = observe._initialized

    # Fresh init per test with auto_inject enabled (default)
    if was_initialized:
        observe.shutdown()

    observe.init(
        backend_url="http://localhost:8000",
        batch_size=1,
        flush_interval=0.01,
        auto_inject=True,  # Enable auto-injection
    )

    yield captured

    try:
        if observe._initialized:
            observe.flush()
    finally:
        if observe._initialized:
            observe.shutdown()


@pytest.mark.skipif(not OPENAI_API_KEY, reason="OPENAI_API_KEY not set")
def test_auto_injection_simple_llm(capture_backend):
    """Test that LLM calls are auto-tracked without explicit callbacks parameter."""
    from langchain_openai import ChatOpenAI

    captured = capture_backend

    # Create LLM WITHOUT passing callbacks parameter
    # (Auto-injection should handle this)
    llm = ChatOpenAI(model="gpt-3.5-turbo")
    response = llm.invoke("Say hello in 5 words")

    observe.flush()

    # Verify events were captured without explicit callbacks
    llm_events = [e for e in captured if isinstance(e, LLMCallEvent)]
    assert (
        len(llm_events) >= 2
    ), f"Expected at least 2 LLM events with auto-injection, got {len(llm_events)}"

    start = next(e for e in llm_events if e.data.get("status") == "started")
    end = next(e for e in llm_events if e.data.get("status") == "completed")

    assert "Say hello in 5 words" in (start.prompt or "")
    assert isinstance(end.completion, str) and len(end.completion) > 0
    assert end.tokens_in >= 0 and end.tokens_out >= 0


@pytest.mark.skipif(not OPENAI_API_KEY, reason="OPENAI_API_KEY not set")
def test_auto_injection_respects_explicit_callbacks(capture_backend):
    """Test that explicit callbacks are respected and not overridden."""
    from langchain_openai import ChatOpenAI
    from gati.instrumentation.langchain import GatiLangChainCallback

    captured = capture_backend

    # Create callback explicitly
    callback = GatiLangChainCallback()

    # Create LLM WITH explicit callbacks
    llm = ChatOpenAI(model="gpt-3.5-turbo", callbacks=[callback])
    response = llm.invoke("Hello")

    observe.flush()

    # Should still work and capture events
    llm_events = [e for e in captured if isinstance(e, LLMCallEvent)]
    assert (
        len(llm_events) >= 1
    ), "Expected events with explicit callbacks"


@pytest.mark.skipif(not OPENAI_API_KEY, reason="OPENAI_API_KEY not set")
def test_auto_injection_with_agent(capture_backend):
    """Test that auto-injection works with agents and tools."""
    from langchain_openai import ChatOpenAI
    from langchain.agents import create_tool_calling_agent, AgentExecutor
    from langchain.tools import tool
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

    captured = capture_backend

    @tool
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    tools = [add]

    # Create LLM WITHOUT callbacks parameter (auto-injection should handle it)
    llm = ChatOpenAI(model="gpt-3.5-turbo")

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful math assistant."),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)

    # Create executor WITHOUT callbacks parameter (auto-injection should handle it)
    executor = AgentExecutor(agent=agent, tools=tools, verbose=False)

    result = executor.invoke({"input": "What is 2 + 2?"})

    observe.flush()

    # Verify LLM events were captured via auto-injection
    llm_events = [e for e in captured if isinstance(e, LLMCallEvent)]
    assert (
        len(llm_events) > 0
    ), "Expected LLM events to be captured via auto-injection"


def test_auto_injection_can_be_disabled(monkeypatch):
    """Test that auto-injection can be disabled via auto_inject=False."""
    from gati.instrumentation import langchain as langchain_module

    # Reset observe singleton for this test
    captured = []

    def capture_send_events(self, events):
        captured.extend(events)

    monkeypatch.setattr("gati.core.client.EventClient.send_events", capture_send_events)

    # First disable auto-injection from any previous test
    if langchain_module._AUTO_INJECTION_ENABLED:
        langchain_module.disable_auto_injection()

    # Shutdown any previously initialized observe
    if observe._initialized:
        observe.shutdown()

    # Initialize with auto_inject=False
    observe.init(
        backend_url="http://localhost:8000",
        batch_size=1,
        flush_interval=0.01,
        auto_inject=False,  # Disable auto-injection
    )

    # Verify auto-injection is not enabled
    assert not langchain_module._AUTO_INJECTION_ENABLED, \
        "Auto-injection should be disabled when auto_inject=False"

    observe.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
