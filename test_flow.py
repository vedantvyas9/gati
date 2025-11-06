#!/usr/bin/env python
"""
Test script to send events to the GATI backend.
This script demonstrates the end-to-end flow:
1. Start backend (already done)
2. Send events to backend
3. Query APIs to verify data
4. Check database
"""

import requests
import json
from datetime import datetime
import uuid

BASE_URL = "http://localhost:8000"
RUN_ID = str(uuid.uuid4())
AGENT_NAME = "test_agent"

def test_health():
    """Test the health endpoint."""
    print("\n=== Testing Health Endpoint ===")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 200


def send_events():
    """Send test events to the backend."""
    print("\n=== Sending Test Events ===")

    events = [
        {
            "event_type": "agent_start",
            "run_id": RUN_ID,
            "agent_name": AGENT_NAME,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": {"input": "test input"}
        },
        {
            "event_type": "llm_call",
            "run_id": RUN_ID,
            "agent_name": AGENT_NAME,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": {"model": "gpt-4", "tokens_in": 100, "tokens_out": 50}
        },
        {
            "event_type": "tool_call",
            "run_id": RUN_ID,
            "agent_name": AGENT_NAME,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": {"tool_name": "search", "input": "test query"}
        },
        {
            "event_type": "agent_end",
            "run_id": RUN_ID,
            "agent_name": AGENT_NAME,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": {"output": "test output", "duration_ms": 1000}
        }
    ]

    response = requests.post(
        f"{BASE_URL}/api/events",
        json={"events": events}
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 200


def query_agents():
    """Query the agents API."""
    print("\n=== Querying Agents ===")
    response = requests.get(f"{BASE_URL}/api/agents")
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    return response.status_code == 200 and len(data) > 0


def query_agent_details():
    """Query agent details."""
    print(f"\n=== Querying Agent Details ({AGENT_NAME}) ===")
    response = requests.get(f"{BASE_URL}/api/agents/{AGENT_NAME}")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200


def query_agent_metrics():
    """Query agent metrics."""
    print(f"\n=== Querying Agent Metrics ({AGENT_NAME}) ===")
    response = requests.get(f"{BASE_URL}/api/agents/{AGENT_NAME}/metrics")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200


def query_run_details():
    """Query run details."""
    print(f"\n=== Querying Run Details ({RUN_ID}) ===")
    response = requests.get(f"{BASE_URL}/api/runs/{RUN_ID}")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200


def query_run_timeline():
    """Query run timeline."""
    print(f"\n=== Querying Run Timeline ({RUN_ID}) ===")
    response = requests.get(f"{BASE_URL}/api/runs/{RUN_ID}/timeline")
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Events Count: {len(data.get('events', []))}")
    print(f"Response: {json.dumps(data, indent=2)}")
    return response.status_code == 200 and len(data.get('events', [])) == 4


def query_global_metrics():
    """Query global metrics."""
    print("\n=== Querying Global Metrics ===")
    response = requests.get(f"{BASE_URL}/api/metrics/summary")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200


def main():
    """Run all tests."""
    print("=" * 60)
    print("GATI Backend Test Flow")
    print("=" * 60)

    results = {}

    # 1. Test health
    results['health'] = test_health()

    # 2. Send events
    results['send_events'] = send_events()

    # 3. Query agents
    results['query_agents'] = query_agents()

    # 4. Query agent details
    results['agent_details'] = query_agent_details()

    # 5. Query agent metrics
    results['agent_metrics'] = query_agent_metrics()

    # 6. Query run details
    results['run_details'] = query_run_details()

    # 7. Query run timeline
    results['run_timeline'] = query_run_timeline()

    # 8. Query global metrics
    results['global_metrics'] = query_global_metrics()

    # Summary
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name:30} {status}")

    all_passed = all(results.values())
    print("=" * 60)
    if all_passed:
        print("✓ All tests PASSED!")
    else:
        print("✗ Some tests FAILED!")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
