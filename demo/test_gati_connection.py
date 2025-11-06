"""
Test script to verify GATI SDK connection and event sending.
"""
import time
from gati import observe
from gati.core.event import LLMCallEvent

# Initialize GATI
print("Initializing GATI...")
observe.init(
    backend_url="http://localhost:8000",
    agent_name="test_agent",
    batch_size=1,  # Send immediately
    flush_interval=1.0
)
print("GATI initialized")

# Create a test event
print("\nCreating test event...")
test_event = LLMCallEvent(
    run_id="test-run-123",
    agent_name="test_agent",
    model="gpt-4o-mini",
    prompt="test prompt",
    completion="test completion",
    tokens_in=10,
    tokens_out=20,
    cost=0.001,
    latency_ms=100.0
)

print("Tracking event...")
observe.track_event(test_event)

print("Waiting for buffer to flush...")
time.sleep(2)

print("Manually flushing...")
observe.flush()

print("\nTest complete. Check the backend logs and database.")
print("You should see a POST request to /api/events")
