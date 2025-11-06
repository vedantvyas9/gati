"""End-to-end test for system prompt extraction with real LangChain usage."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from gati import observe
from gati.core.event import LLMCallEvent


def test_system_prompt_extraction_with_explicit_callbacks():
    """Test system prompt extraction when using explicit callbacks."""

    # Mock the backend to capture events
    captured_events = []

    def mock_track_event(event):
        captured_events.append(event)

    with patch('gati.instrumentation.langchain.observe.track_event', side_effect=mock_track_event):
        from langchain_openai import ChatOpenAI
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.messages import SystemMessage, HumanMessage

        # Initialize observe
        observe.init(backend_url="http://localhost:8000", agent_name="test-agent")

        # Create a prompt with system message
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful math tutor. Always explain your reasoning."),
            ("human", "{question}")
        ])

        # Create LLM with explicit callbacks
        llm = ChatOpenAI(model="gpt-3.5-turbo", callbacks=observe.get_callbacks())

        # Create chain
        chain = prompt | llm

        # Mock the actual LLM call to avoid real API calls
        with patch.object(llm.client.chat.completions, 'create') as mock_create:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "2+2 equals 4"
            mock_response.usage = Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
            mock_response.model = "gpt-3.5-turbo"
            mock_create.return_value = mock_response

            # Invoke chain
            try:
                result = chain.invoke({"question": "What is 2+2?"})
            except Exception as e:
                # Some mock issues are okay for this test
                pass

    # Find LLM start events
    llm_start_events = [e for e in captured_events if isinstance(e, LLMCallEvent) and e.data.get("status") == "started"]

    # Verify we captured at least one event
    assert len(llm_start_events) > 0, f"Expected at least 1 LLM start event, got {len(llm_start_events)}"

    # Verify system prompt was extracted
    event = llm_start_events[0]
    assert event.system_prompt != "", f"System prompt should not be empty"
    assert "math tutor" in event.system_prompt.lower(), f"System prompt should contain 'math tutor', got: {event.system_prompt}"

    # Verify user prompt was extracted separately
    assert event.prompt != "", f"User prompt should not be empty"
    assert "2+2" in event.prompt or "question" in event.prompt.lower(), f"User prompt should contain question, got: {event.prompt}"


def test_system_prompt_with_mock_callback():
    """Test system prompt extraction at callback level with mock data."""
    from gati.instrumentation.langchain import GatiLangChainCallback
    from langchain_core.messages import SystemMessage, HumanMessage

    captured_events = []

    def mock_track_event(event):
        captured_events.append(event)

    with patch('gati.instrumentation.langchain.observe.track_event', side_effect=mock_track_event):
        with patch('gati.instrumentation.langchain.get_current_run_id', return_value="test-run-123"):
            with patch('gati.instrumentation.langchain.get_parent_event_id', return_value=None):
                callback = GatiLangChainCallback()

                # Simulate LangChain calling with message objects
                system_msg = SystemMessage(content="You are a coding expert.")
                human_msg = HumanMessage(content="Write a Python function to sort a list.")

                serialized = {"name": "ChatOpenAI"}
                prompts = [[system_msg, human_msg]]

                callback.on_llm_start(
                    serialized=serialized,
                    prompts=prompts,
                    run_id="lc-123"
                )

    # Verify event was captured
    assert len(captured_events) == 1
    event = captured_events[0]

    # Verify system prompt extraction
    assert isinstance(event, LLMCallEvent)
    assert event.system_prompt == "You are a coding expert."
    assert event.prompt == "Write a Python function to sort a list."


def test_no_system_prompt_fallback():
    """Test that callback handles prompts without system messages."""
    from gati.instrumentation.langchain import GatiLangChainCallback

    captured_events = []

    def mock_track_event(event):
        captured_events.append(event)

    with patch('gati.instrumentation.langchain.observe.track_event', side_effect=mock_track_event):
        with patch('gati.instrumentation.langchain.get_current_run_id', return_value="test-run-123"):
            with patch('gati.instrumentation.langchain.get_parent_event_id', return_value=None):
                callback = GatiLangChainCallback()

                # Simple string prompt with no system message
                serialized = {"name": "OpenAI"}
                prompts = ["Tell me a joke about programming."]

                callback.on_llm_start(
                    serialized=serialized,
                    prompts=prompts,
                    run_id="lc-456"
                )

    # Verify event was captured
    assert len(captured_events) == 1
    event = captured_events[0]

    # Verify no system prompt (empty string)
    assert event.system_prompt == ""

    # Verify user prompt is captured
    assert event.prompt == "Tell me a joke about programming."


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
