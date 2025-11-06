"""Day 1 tests for GATI SDK.

Tests:
1. Events can be created and serialized to JSON
2. Config loads correctly with defaults
3. EventBuffer batches events and flushes on size/interval
4. EventClient can send events (mock the HTTP call)
5. Context manager properly tracks run_ids
6. Decorators work on sample functions and capture data
7. Full flow: init observe → track events → buffer → client
"""
import json
import time
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from gati.core.event import (
    Event,
    LLMCallEvent,
    ToolCallEvent,
    AgentStartEvent,
    AgentEndEvent,
    StepEvent,
)
from gati.core.config import Config
from gati.core.buffer import EventBuffer
from gati.core.client import EventClient
from gati.core.context import RunContextManager, run_context, get_current_run_id
from gati.observe import Observe, observe
from gati.decorators.track_tool import track_tool
from gati.decorators.track_step import track_step
from gati.decorators.track_agent import track_agent


# ============================================================================
# Test 1: Events can be created and serialized to JSON
# ============================================================================

def test_event_creation_and_serialization():
    """Test that events can be created and serialized to JSON."""
    # Test base Event
    event = Event(
        event_type="test_event",
        run_id="test-run-123",
        agent_name="test_agent",
        data={"key": "value"}
    )
    
    assert event.event_type == "test_event"
    assert event.run_id == "test-run-123"
    assert event.agent_name == "test_agent"
    assert event.data == {"key": "value"}
    assert event.timestamp  # Should be auto-generated
    
    # Test to_dict
    event_dict = event.to_dict()
    assert isinstance(event_dict, dict)
    assert event_dict["event_type"] == "test_event"
    assert event_dict["run_id"] == "test-run-123"
    
    # Test to_json
    event_json = event.to_json()
    assert isinstance(event_json, str)
    parsed = json.loads(event_json)
    assert parsed["event_type"] == "test_event"
    assert parsed["run_id"] == "test-run-123"


def test_llm_call_event_serialization():
    """Test LLMCallEvent creation and serialization."""
    event = LLMCallEvent(
        run_id="run-123",
        agent_name="test_agent",
        model="gpt-4",
        prompt="Hello",
        completion="Hi there",
        tokens_in=10,
        tokens_out=5,
        latency_ms=150.5,
        cost=0.001
    )
    
    assert event.event_type == "llm_call"
    assert event.model == "gpt-4"
    
    event_dict = event.to_dict()
    assert event_dict["event_type"] == "llm_call"
    assert event_dict["data"]["model"] == "gpt-4"
    assert event_dict["data"]["tokens_in"] == 10
    
    # Test JSON serialization
    event_json = event.to_json()
    parsed = json.loads(event_json)
    assert parsed["data"]["model"] == "gpt-4"


def test_tool_call_event_serialization():
    """Test ToolCallEvent creation and serialization."""
    event = ToolCallEvent(
        run_id="run-123",
        tool_name="search_api",
        input={"query": "test"},
        output={"results": ["result1"]},
        latency_ms=50.0
    )
    
    assert event.event_type == "tool_call"
    assert event.tool_name == "search_api"
    
    event_json = event.to_json()
    parsed = json.loads(event_json)
    assert parsed["event_type"] == "tool_call"
    assert parsed["data"]["tool_name"] == "search_api"


def test_agent_start_end_events_serialization():
    """Test AgentStartEvent and AgentEndEvent serialization."""
    start_event = AgentStartEvent(
        run_id="run-123",
        agent_name="my_agent",
        input={"prompt": "test"},
        metadata={"version": "1.0"}
    )
    
    assert start_event.event_type == "agent_start"
    assert start_event.data["input"]["prompt"] == "test"
    
    end_event = AgentEndEvent(
        run_id="run-123",
        agent_name="my_agent",
        output={"result": "success"},
        total_duration_ms=1000.0,
        total_cost=0.01
    )
    
    assert end_event.event_type == "agent_end"
    assert end_event.data["total_duration_ms"] == 1000.0
    
    # Test JSON serialization
    start_json = start_event.to_json()
    end_json = end_event.to_json()
    
    assert json.loads(start_json)["event_type"] == "agent_start"
    assert json.loads(end_json)["event_type"] == "agent_end"


# ============================================================================
# Test 2: Config loads correctly with defaults
# ============================================================================

def test_config_defaults():
    """Test that Config loads correctly with defaults."""
    # Reset config to ensure clean state
    Config._instance = None
    Config._initialized = False
    
    with patch.dict("os.environ", {}, clear=True):
        config = Config()
        
        assert config.agent_name == "default_agent"
        assert config.environment == "development"
        assert config.backend_url == "http://localhost:8000"
        assert config.batch_size == 100
        assert config.flush_interval == 5.0
        assert config.telemetry is True
        assert config.api_key is None


def test_config_environment_variables():
    """Test that Config respects environment variables."""
    # Reset config
    Config._instance = None
    Config._initialized = False
    
    env_vars = {
        "GATI_AGENT_NAME": "test_agent",
        "GATI_ENVIRONMENT": "production",
        "GATI_BACKEND_URL": "https://api.example.com",
        "GATI_BATCH_SIZE": "50",
        "GATI_FLUSH_INTERVAL": "10.0",
        "GATI_TELEMETRY": "false",
        "GATI_API_KEY": "test-key-123"
    }
    
    with patch.dict("os.environ", env_vars, clear=True):
        config = Config()
        
        assert config.agent_name == "test_agent"
        assert config.environment == "production"
        assert config.backend_url == "https://api.example.com"
        assert config.batch_size == 50
        assert config.flush_interval == 10.0
        assert config.telemetry is False
        assert config.api_key == "test-key-123"


def test_config_update():
    """Test that Config.update() works correctly."""
    # Reset config
    Config._instance = None
    Config._initialized = False
    
    with patch.dict("os.environ", {}, clear=True):
        config = Config()
        
        config.update(
            agent_name="updated_agent",
            batch_size=200,
            flush_interval=15.0
        )
        
        assert config.agent_name == "updated_agent"
        assert config.batch_size == 200
        assert config.flush_interval == 15.0


# ============================================================================
# Test 3: EventBuffer batches events and flushes on size/interval
# ============================================================================

def test_event_buffer_batch_size_flush():
    """Test that EventBuffer flushes when batch size is reached."""
    flushed_events = []
    
    def flush_callback(events):
        flushed_events.extend(events)
    
    buffer = EventBuffer(
        flush_callback=flush_callback,
        batch_size=3,
        flush_interval=10.0
    )
    
    # Add events up to batch size
    event1 = Event(event_type="test1")
    event2 = Event(event_type="test2")
    event3 = Event(event_type="test3")
    
    buffer.add_event(event1)
    assert len(flushed_events) == 0
    
    buffer.add_event(event2)
    assert len(flushed_events) == 0
    
    buffer.add_event(event3)  # Should trigger flush
    assert len(flushed_events) == 3
    assert flushed_events[0].event_type == "test1"
    assert flushed_events[1].event_type == "test2"
    assert flushed_events[2].event_type == "test3"
    
    # Buffer should be empty after flush
    assert len(buffer) == 0
    
    buffer.stop()


def test_event_buffer_manual_flush():
    """Test that EventBuffer can be manually flushed."""
    flushed_events = []
    
    def flush_callback(events):
        flushed_events.extend(events)
    
    buffer = EventBuffer(
        flush_callback=flush_callback,
        batch_size=10,
        flush_interval=10.0
    )
    
    event1 = Event(event_type="test1")
    event2 = Event(event_type="test2")
    
    buffer.add_event(event1)
    buffer.add_event(event2)
    
    assert len(flushed_events) == 0
    assert len(buffer) == 2
    
    buffer.flush()
    
    assert len(flushed_events) == 2
    assert len(buffer) == 0
    
    buffer.stop()


def test_event_buffer_interval_flush():
    """Test that EventBuffer flushes on interval."""
    flushed_events = []
    
    def flush_callback(events):
        flushed_events.extend(events)
    
    buffer = EventBuffer(
        flush_callback=flush_callback,
        batch_size=100,
        flush_interval=0.1  # Very short interval for testing
    )
    
    buffer.start()
    
    event1 = Event(event_type="test1")
    buffer.add_event(event1)
    
    # Wait for flush interval
    time.sleep(0.15)
    
    # Should have flushed
    assert len(flushed_events) >= 1
    
    buffer.stop()


def test_event_buffer_context_manager():
    """Test that EventBuffer works as a context manager."""
    flushed_events = []
    
    def flush_callback(events):
        flushed_events.extend(events)
    
    with EventBuffer(flush_callback=flush_callback, batch_size=2) as buffer:
        buffer.add_event(Event(event_type="test1"))
        buffer.add_event(Event(event_type="test2"))
    
    # Should have flushed on exit
    assert len(flushed_events) >= 2


# ============================================================================
# Test 4: EventClient can send events (mock the HTTP call)
# ============================================================================

@patch('gati.core.client.requests.Session')
def test_event_client_send_events(mock_session_class):
    """Test that EventClient can send events."""
    # Setup mock
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_session.post.return_value = mock_response
    # Set up headers as a dict-like object
    mock_session.headers = {}
    mock_session_class.return_value = mock_session
    
    # Reset config
    Config._instance = None
    Config._initialized = False
    
    with patch.dict("os.environ", {}, clear=True):
        client = EventClient(
            backend_url="http://localhost:8000",
            api_key="test-key"
        )
        
        events = [
            Event(event_type="test1", run_id="run-1"),
            Event(event_type="test2", run_id="run-2")
        ]
        
        client.send_events(events)
        
        # Wait a bit for the background thread to execute
        time.sleep(0.3)
        
        # Verify the request was made
        assert mock_session.post.called
        call_args = mock_session.post.call_args
        
        assert call_args[0][0] == "http://localhost:8000/api/events"
        assert call_args[1]["json"] is not None
        
        # Verify events were sent
        sent_events = call_args[1]["json"]
        assert len(sent_events) == 2
        assert sent_events[0]["event_type"] == "test1"
        assert sent_events[1]["event_type"] == "test2"
        
        # Verify headers were set (they are set during client initialization)
        assert "Content-Type" in mock_session.headers
        assert mock_session.headers["Content-Type"] == "application/json"
        assert "Authorization" in mock_session.headers
        assert mock_session.headers["Authorization"] == "Bearer test-key"
        
        client.close()


@patch('gati.core.client.requests.Session')
def test_event_client_retry_on_failure(mock_session_class):
    """Test that EventClient retries on failure."""
    # Setup mock to fail twice, then succeed
    mock_session = MagicMock()
    mock_response_fail = MagicMock()
    mock_response_fail.status_code = 500
    mock_response_success = MagicMock()
    mock_response_success.status_code = 200
    
    mock_session.post.side_effect = [
        mock_response_fail,
        mock_response_fail,
        mock_response_success
    ]
    mock_session_class.return_value = mock_session
    
    # Reset config
    Config._instance = None
    Config._initialized = False
    
    with patch.dict("os.environ", {}, clear=True):
        client = EventClient(
            backend_url="http://localhost:8000",
            max_retries=2
        )
        
        events = [Event(event_type="test", run_id="run-1")]
        
        # Use sync method directly for testing retries
        events_dict = client._prepare_events(events)
        result = client._send_with_retry(events_dict)
        
        # Should eventually succeed
        assert result is True
        assert mock_session.post.call_count == 3
        
        client.close()


# ============================================================================
# Test 5: Context manager properly tracks run_ids
# ============================================================================

def test_run_context_manager():
    """Test that context manager properly tracks run_ids."""
    # Clear context first
    RunContextManager.clear_context()
    
    # Test single context
    with run_context(run_id="run-1") as run_id:
        assert run_id == "run-1"
        assert get_current_run_id() == "run-1"
        assert RunContextManager.get_depth() == 1
    
    # Should be cleared after exit
    assert get_current_run_id() is None
    assert RunContextManager.get_depth() == 0


def test_nested_run_context():
    """Test nested run contexts."""
    RunContextManager.clear_context()
    
    with run_context(run_id="parent-run") as parent_id:
        assert get_current_run_id() == "parent-run"
        assert RunContextManager.get_depth() == 1
        
        with run_context(run_id="child-run") as child_id:
            assert get_current_run_id() == "child-run"
            assert RunContextManager.get_depth() == 2
            
            # Check parent relationship
            parent_run_id = RunContextManager.get_parent_run_id()
            assert parent_run_id == "parent-run"
        
        # Should be back to parent
        assert get_current_run_id() == "parent-run"
        assert RunContextManager.get_depth() == 1
    
    # Should be cleared
    assert get_current_run_id() is None


def test_run_context_auto_generate_id():
    """Test that run_context auto-generates IDs when not provided."""
    RunContextManager.clear_context()
    
    with run_context() as run_id:
        assert run_id is not None
        assert len(run_id) > 0
        assert get_current_run_id() == run_id
    
    assert get_current_run_id() is None


def test_run_context_set_run_id():
    """Test that set_run_id works correctly."""
    RunContextManager.clear_context()
    
    with run_context(run_id="initial-run") as _:
        assert get_current_run_id() == "initial-run"
        
        RunContextManager.set_run_id("new-run")
        assert get_current_run_id() == "new-run"
    
    # Clear context after test to ensure clean state
    RunContextManager.clear_context()
    assert get_current_run_id() is None


# ============================================================================
# Test 6: Decorators work on sample functions and capture data
# ============================================================================

def test_track_tool_decorator():
    """Test that @track_tool decorator works and captures data."""
    # Reset observe singleton
    Observe._instance = None
    Observe._initialized = False
    
    # Track events
    tracked_events = []
    
    def mock_track_event(event):
        tracked_events.append(event)
    
    # Setup observe
    observe._initialized = True
    observe.track_event = mock_track_event
    
    # Clear context
    RunContextManager.clear_context()
    
    with run_context(run_id="test-run"):
        @track_tool
        def sample_tool(x: int, y: int) -> int:
            """Sample tool function."""
            return x + y
        
        result = sample_tool(5, 3)
        
        assert result == 8
        assert len(tracked_events) == 1
        
        event = tracked_events[0]
        assert event.event_type == "tool_call"
        assert event.tool_name == "sample_tool"
        assert event.run_id == "test-run"
        assert "x" in event.data["input"]
        assert "y" in event.data["input"]
        assert event.data["input"]["x"] == 5
        assert event.data["input"]["y"] == 3
        assert event.data["output"] == 8
        assert event.data["latency_ms"] > 0


def test_track_tool_decorator_with_name():
    """Test that @track_tool decorator works with custom name."""
    # Reset observe singleton
    Observe._instance = None
    Observe._initialized = False
    
    tracked_events = []
    
    def mock_track_event(event):
        tracked_events.append(event)
    
    observe._initialized = True
    observe.track_event = mock_track_event
    
    RunContextManager.clear_context()
    
    with run_context(run_id="test-run"):
        @track_tool(name="custom_tool_name")
        def my_function(x: int) -> int:
            return x * 2
        
        result = my_function(5)
        
        assert result == 10
        assert len(tracked_events) == 1
        assert tracked_events[0].tool_name == "custom_tool_name"


def test_track_step_decorator():
    """Test that @track_step decorator works and captures data."""
    # Reset observe singleton
    Observe._instance = None
    Observe._initialized = False
    
    tracked_events = []
    
    def mock_track_event(event):
        tracked_events.append(event)
    
    observe._initialized = True
    observe.track_event = mock_track_event
    
    RunContextManager.clear_context()
    
    with run_context(run_id="test-run"):
        @track_step
        def process_data(data: str) -> str:
            return data.upper()
        
        result = process_data("hello")
        
        assert result == "HELLO"
        assert len(tracked_events) == 1
        
        event = tracked_events[0]
        assert event.event_type == "step"
        assert event.step_name == "process_data"
        assert event.run_id == "test-run"
        assert event.data["output"] == "HELLO"
        assert event.data["duration_ms"] > 0


def test_track_agent_decorator():
    """Test that @track_agent decorator works and captures data."""
    # Reset observe singleton
    Observe._instance = None
    Observe._initialized = False
    
    tracked_events = []
    
    def mock_track_event(event):
        tracked_events.append(event)
    
    observe._initialized = True
    observe.track_event = mock_track_event
    
    @track_agent
    def my_agent(prompt: str) -> str:
        """Sample agent function."""
        return f"Response to: {prompt}"
    
    result = my_agent("test prompt")
    
    assert result == "Response to: test prompt"
    assert len(tracked_events) == 2  # Start and end events
    
    # Check start event
    start_event = tracked_events[0]
    assert start_event.event_type == "agent_start"
    assert start_event.agent_name == "my_agent"
    assert "prompt" in start_event.data["input"]
    
    # Check end event
    end_event = tracked_events[1]
    assert end_event.event_type == "agent_end"
    assert end_event.agent_name == "my_agent"
    assert end_event.data["output"] == "Response to: test prompt"
    assert end_event.data["total_duration_ms"] > 0
    
    # Both should have the same run_id
    assert start_event.run_id == end_event.run_id
    
    # Check that context was set
    # The context should be cleared after the decorator exits
    assert get_current_run_id() is None


def test_track_tool_error_handling():
    """Test that decorators handle errors correctly."""
    # Reset observe singleton
    Observe._instance = None
    Observe._initialized = False
    
    tracked_events = []
    
    def mock_track_event(event):
        tracked_events.append(event)
    
    observe._initialized = True
    observe.track_event = mock_track_event
    
    RunContextManager.clear_context()
    
    with run_context(run_id="test-run"):
        @track_tool
        def failing_tool(x: int) -> int:
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            failing_tool(5)
        
        # Should still track the event with error
        assert len(tracked_events) == 1
        event = tracked_events[0]
        assert "error" in event.data
        assert event.data["error"]["type"] == "ValueError"
        assert event.data["error"]["message"] == "Test error"


# ============================================================================
# Test 7: Full flow: init observe → track events → buffer → client
# ============================================================================

@patch('gati.core.client.requests.Session')
def test_full_flow(mock_session_class):
    """Test the full flow: init observe → track events → buffer → client."""
    # Setup mock HTTP client
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_session.post.return_value = mock_response
    mock_session.headers = {}
    mock_session_class.return_value = mock_session
    
    # Reset all singletons
    Observe._instance = None
    Observe._initialized = False
    Config._instance = None
    Config._initialized = False
    RunContextManager.clear_context()
    
    with patch.dict("os.environ", {}, clear=True):
        # 1. Initialize observe
        observe.init(
            backend_url="http://localhost:8000",
            agent_name="test_agent",
            batch_size=2,  # Small batch size for testing
            flush_interval=5.0,
            api_key="test-key"
        )
        
        assert observe._initialized is True
        assert observe._buffer is not None
        assert observe._client is not None
        
        # Verify client uses the mock session
        assert observe._client._session is mock_session
        
        # 2. Enter run context
        with run_context(run_id="full-flow-run") as run_id:
            # 3. Track events
            event1 = Event(event_type="test1", data={"value": 1})
            event2 = Event(event_type="test2", data={"value": 2})
            event3 = Event(event_type="test3", data={"value": 3})
            
            observe.track_event(event1)
            # Buffer should have 1 event
            assert len(observe._buffer) == 1
            
            observe.track_event(event2)  # Should trigger flush (batch_size=2)
            
            # Wait for the flush to complete (need more time for async thread)
            # Retry mechanism to handle timing issues
            client_session = observe._client._session
            max_retries = 15
            for _ in range(max_retries):
                time.sleep(0.2)
                if client_session.post.called:
                    break
            
            # 4. Verify events were sent to client
            # Check both the mock_session and the client's internal session
            assert client_session.post.called, (
                f"HTTP request should have been made. "
                f"Buffer length: {len(observe._buffer)}, "
                f"Post called: {client_session.post.called}"
            )
            
            # Get the first batch
            first_call = client_session.post.call_args_list[0]
            first_batch = first_call[1]["json"]
            assert len(first_batch) == 2
            assert first_batch[0]["event_type"] == "test1"
            assert first_batch[1]["event_type"] == "test2"
            
            # Track one more event
            observe.track_event(event3)
            
            # Manually flush to ensure it's sent
            observe.flush()
            time.sleep(0.8)
            
            # Verify all events were sent
            assert client_session.post.call_count >= 2
        
        # 5. Shutdown
        observe.shutdown()
        
        assert observe._initialized is False
        assert observe._buffer is None
        assert observe._client is None


@patch('gati.core.client.requests.Session')
def test_full_flow_with_decorators(mock_session_class):
    """Test full flow with decorators."""
    # Setup mock HTTP client
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_session.post.return_value = mock_response
    mock_session.headers = {}
    mock_session_class.return_value = mock_session
    
    # Reset all singletons
    Observe._instance = None
    Observe._initialized = False
    Config._instance = None
    Config._initialized = False
    RunContextManager.clear_context()
    
    with patch.dict("os.environ", {}, clear=True):
        # Initialize observe
        observe.init(
            backend_url="http://localhost:8000",
            agent_name="test_agent",
            batch_size=10,
            flush_interval=5.0
        )
        
        # Verify client uses the mock session
        assert observe._client._session is mock_session
        
        # Use decorator to track agent
        @track_agent
        def my_agent(input_data: str) -> str:
            @track_tool
            def helper_tool(x: int) -> int:
                return x * 2
            
            result = helper_tool(5)
            return f"{input_data}: {result}"
        
        # Execute agent
        result = my_agent("test")
        
        assert result == "test: 10"
        
        # Flush to ensure events are sent
        observe.flush()
        
        # Wait for async thread to complete with retry mechanism
        client_session = observe._client._session
        max_retries = 15
        for _ in range(max_retries):
            time.sleep(0.2)
            if client_session.post.called:
                break
        
        # Verify events were sent
        assert client_session.post.called, (
            f"HTTP request should have been made. "
            f"Buffer length: {len(observe._buffer)}, "
            f"Post called: {client_session.post.called}"
        )
        
        # Get all events that were sent
        all_events = []
        for call in client_session.post.call_args_list:
            events = call[1]["json"]
            all_events.extend(events)
        
        # Should have at least agent_start, agent_end, and tool_call events
        event_types = [e["event_type"] for e in all_events]
        assert "agent_start" in event_types
        assert "agent_end" in event_types
        assert "tool_call" in event_types
        
        # Cleanup
        observe.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

