"""Test system prompt extraction and transmission for LangChain."""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from gati.instrumentation.langchain import GatiLangChainCallback
from gati.core.event import LLMCallEvent


class TestSystemPromptExtraction:
    """Test system prompt extraction from various LangChain prompt formats."""

    def test_extract_system_and_user_prompts_string_only(self):
        """Test extraction with simple string prompts."""
        callback = GatiLangChainCallback()
        prompts = ["Hello, how are you?"]

        system_prompt, user_prompt = callback._extract_system_and_user_prompts(prompts)

        assert system_prompt == ""
        assert user_prompt == "Hello, how are you?"

    def test_extract_system_and_user_prompts_multiple_strings(self):
        """Test extraction with multiple string prompts."""
        callback = GatiLangChainCallback()
        prompts = ["First prompt", "Second prompt"]

        system_prompt, user_prompt = callback._extract_system_and_user_prompts(prompts)

        assert system_prompt == ""
        assert user_prompt == "First prompt\n\nSecond prompt"

    def test_extract_system_and_user_prompts_dict_format(self):
        """Test extraction with dict-based messages."""
        callback = GatiLangChainCallback()
        prompts = [
            [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is 2+2?"}
            ]
        ]

        system_prompt, user_prompt = callback._extract_system_and_user_prompts(prompts)

        assert system_prompt == "You are a helpful assistant."
        assert user_prompt == "What is 2+2?"

    def test_extract_system_and_user_prompts_object_with_type_attribute(self):
        """Test extraction with message objects having 'type' attribute."""
        callback = GatiLangChainCallback()

        # Mock message objects
        system_msg = Mock()
        system_msg.type = "system"
        system_msg.content = "You are a coding assistant."

        user_msg = Mock()
        user_msg.type = "human"
        user_msg.content = "Write a Python function."

        prompts = [[system_msg, user_msg]]

        system_prompt, user_prompt = callback._extract_system_and_user_prompts(prompts)

        assert system_prompt == "You are a coding assistant."
        assert user_prompt == "Write a Python function."

    def test_extract_system_and_user_prompts_class_name_detection(self):
        """Test extraction using class name detection."""
        callback = GatiLangChainCallback()

        # Mock message with SystemMessage class name
        class SystemMessage:
            def __init__(self, content):
                self.content = content

        class HumanMessage:
            def __init__(self, content):
                self.content = content

        system_msg = SystemMessage("You are an expert.")
        human_msg = HumanMessage("Help me understand.")

        prompts = [[system_msg, human_msg]]

        system_prompt, user_prompt = callback._extract_system_and_user_prompts(prompts)

        assert system_prompt == "You are an expert."
        assert user_prompt == "Help me understand."

    def test_extract_system_and_user_prompts_multiple_system_messages(self):
        """Test extraction with multiple system messages."""
        callback = GatiLangChainCallback()
        prompts = [
            [
                {"role": "system", "content": "You are helpful."},
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": "Hello"}
            ]
        ]

        system_prompt, user_prompt = callback._extract_system_and_user_prompts(prompts)

        assert system_prompt == "You are helpful.\n\nBe concise."
        assert user_prompt == "Hello"

    def test_extract_system_and_user_prompts_with_ai_messages(self):
        """Test extraction with AI/assistant messages included."""
        callback = GatiLangChainCallback()
        prompts = [
            [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "What is AI?"},
                {"role": "assistant", "content": "AI stands for..."}
            ]
        ]

        system_prompt, user_prompt = callback._extract_system_and_user_prompts(prompts)

        assert system_prompt == "You are helpful."
        assert "What is AI?" in user_prompt
        assert "AI stands for..." in user_prompt

    def test_extract_system_and_user_prompts_empty_list(self):
        """Test extraction with empty prompt list."""
        callback = GatiLangChainCallback()
        prompts = []

        system_prompt, user_prompt = callback._extract_system_and_user_prompts(prompts)

        assert system_prompt == ""
        assert user_prompt == ""

    def test_extract_system_and_user_prompts_none(self):
        """Test extraction with None."""
        callback = GatiLangChainCallback()

        system_prompt, user_prompt = callback._extract_system_and_user_prompts(None)

        assert system_prompt == ""
        assert user_prompt == ""

    def test_extract_system_and_user_prompts_mixed_formats(self):
        """Test extraction with mixed string and message formats."""
        callback = GatiLangChainCallback()

        system_msg = Mock()
        system_msg.type = "system"
        system_msg.content = "System instruction"

        prompts = [
            [system_msg],
            "Additional user context"
        ]

        system_prompt, user_prompt = callback._extract_system_and_user_prompts(prompts)

        assert system_prompt == "System instruction"
        assert user_prompt == "Additional user context"


class TestLLMCallEventWithSystemPrompt:
    """Test that LLMCallEvent properly handles system_prompt field."""

    def test_llm_call_event_includes_system_prompt(self):
        """Test that LLMCallEvent includes system_prompt in data."""
        event = LLMCallEvent(
            run_id="test-run-123",
            model="gpt-4",
            prompt="User message",
            system_prompt="You are a helpful assistant.",
            completion="Response",
            tokens_in=10,
            tokens_out=20,
            latency_ms=150.5,
            cost=0.001
        )

        # Check that system_prompt is in the event
        assert event.system_prompt == "You are a helpful assistant."

        # Check that it's included in the data dict
        assert event.data["system_prompt"] == "You are a helpful assistant."

        # Check that to_dict includes it
        event_dict = event.to_dict()
        assert event_dict["system_prompt"] == "You are a helpful assistant."
        assert event_dict["prompt"] == "User message"

    def test_llm_call_event_empty_system_prompt(self):
        """Test that LLMCallEvent handles empty system_prompt."""
        event = LLMCallEvent(
            run_id="test-run-123",
            model="gpt-4",
            prompt="User message",
            system_prompt="",
            completion="Response"
        )

        assert event.system_prompt == ""
        assert event.data["system_prompt"] == ""

        event_dict = event.to_dict()
        assert "system_prompt" in event_dict
        assert event_dict["system_prompt"] == ""


class TestLangChainCallbackWithSystemPrompt:
    """Test LangChain callback integration with system prompt extraction."""

    @patch('gati.instrumentation.langchain.observe.track_event')
    @patch('gati.instrumentation.langchain.get_current_run_id')
    @patch('gati.instrumentation.langchain.get_parent_event_id')
    def test_on_llm_start_extracts_system_prompt(self, mock_parent_event_id, mock_run_id, mock_track_event):
        """Test that on_llm_start properly extracts and tracks system prompt."""
        mock_run_id.return_value = "test-run-123"
        mock_parent_event_id.return_value = None

        callback = GatiLangChainCallback()

        # Simulate LangChain calling on_llm_start with messages
        serialized = {"name": "ChatOpenAI"}
        prompts = [
            [
                {"role": "system", "content": "You are a math tutor."},
                {"role": "user", "content": "What is 5+3?"}
            ]
        ]

        callback.on_llm_start(
            serialized=serialized,
            prompts=prompts,
            run_id="lc-run-456"
        )

        # Verify track_event was called
        assert mock_track_event.called

        # Get the event that was tracked
        tracked_event = mock_track_event.call_args[0][0]

        # Verify it's an LLMCallEvent
        assert isinstance(tracked_event, LLMCallEvent)

        # Verify system prompt was extracted
        assert tracked_event.system_prompt == "You are a math tutor."

        # Verify user prompt was extracted
        assert tracked_event.prompt == "What is 5+3?"

        # Verify model name
        assert tracked_event.model == "ChatOpenAI"

    @patch('gati.instrumentation.langchain.observe.track_event')
    @patch('gati.instrumentation.langchain.get_current_run_id')
    @patch('gati.instrumentation.langchain.get_parent_event_id')
    def test_on_llm_start_string_prompts_no_system(self, mock_parent_event_id, mock_run_id, mock_track_event):
        """Test that on_llm_start handles string prompts with no system message."""
        mock_run_id.return_value = "test-run-123"
        mock_parent_event_id.return_value = None

        callback = GatiLangChainCallback()

        serialized = {"name": "OpenAI"}
        prompts = ["Tell me a joke."]

        callback.on_llm_start(
            serialized=serialized,
            prompts=prompts,
            run_id="lc-run-789"
        )

        tracked_event = mock_track_event.call_args[0][0]

        # Should have empty system prompt
        assert tracked_event.system_prompt == ""

        # Should have user prompt
        assert tracked_event.prompt == "Tell me a joke."

    @patch('gati.instrumentation.langchain.observe.track_event')
    @patch('gati.instrumentation.langchain.get_current_run_id')
    @patch('gati.instrumentation.langchain.get_parent_event_id')
    def test_on_llm_start_multiple_system_prompts(self, mock_parent_event_id, mock_run_id, mock_track_event):
        """Test handling of multiple system prompts."""
        mock_run_id.return_value = "test-run-123"
        mock_parent_event_id.return_value = None

        callback = GatiLangChainCallback()

        serialized = {"name": "ChatOpenAI"}
        prompts = [
            [
                {"role": "system", "content": "You are helpful."},
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": "Explain AI."}
            ]
        ]

        callback.on_llm_start(
            serialized=serialized,
            prompts=prompts,
            run_id="lc-run-999"
        )

        tracked_event = mock_track_event.call_args[0][0]

        # Should combine multiple system prompts
        assert "You are helpful." in tracked_event.system_prompt
        assert "Be concise." in tracked_event.system_prompt

        # User prompt should be separate
        assert tracked_event.prompt == "Explain AI."


class TestBackendTransmission:
    """Test that events with system_prompt are properly transmitted to backend."""

    def test_event_serialization_includes_system_prompt(self):
        """Test that event serialization includes all fields including system_prompt."""
        event = LLMCallEvent(
            run_id="test-123",
            model="gpt-4",
            prompt="User question",
            system_prompt="System instruction",
            completion="AI response",
            tokens_in=5,
            tokens_out=10,
            latency_ms=100.0,
            cost=0.001
        )

        # Convert to dict (this is what gets sent to backend)
        event_dict = event.to_dict()

        # Verify all tracking requirements are met
        assert event_dict["system_prompt"] == "System instruction"
        assert event_dict["prompt"] == "User question"
        assert event_dict["model"] == "gpt-4"
        assert event_dict["tokens_in"] == 5
        assert event_dict["tokens_out"] == 10
        assert event_dict["latency_ms"] == 100.0
        assert event_dict["run_id"] == "test-123"
        assert event_dict["event_type"] == "llm_call"

        # Verify it can be JSON serialized
        import json
        json_str = event.to_json()
        assert "System instruction" in json_str
        assert "User question" in json_str

    @patch('requests.Session.post')
    def test_client_sends_system_prompt_to_backend(self, mock_post):
        """Test that EventClient properly sends system_prompt to backend."""
        from gati.core.client import EventClient

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        client = EventClient(
            backend_url="http://localhost:8000",
            api_key="test-key"
        )

        event = LLMCallEvent(
            run_id="test-123",
            model="gpt-4",
            prompt="User message",
            system_prompt="System message",
            completion="Response"
        )

        # Send synchronously for testing
        events_dict = client._prepare_events([event])
        client._send_with_retry(events_dict)

        # Verify post was called
        assert mock_post.called

        # Get the JSON payload that was sent
        call_args = mock_post.call_args
        sent_data = call_args.kwargs['json']

        # Verify the event batch structure
        assert 'events' in sent_data
        assert len(sent_data['events']) == 1

        # Verify system_prompt is in the sent data
        sent_event = sent_data['events'][0]
        assert sent_event['system_prompt'] == "System message"
        assert sent_event['prompt'] == "User message"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
