"""Check events via REST API."""
import requests
import json

BASE_URL = "http://localhost:8000/api"

def check_events():
    """Check events via REST API."""
    print("=" * 80)
    print("GATI Database Event Summary (via REST API)")
    print("=" * 80)

    # Check if backend is running
    try:
        health = requests.get("http://localhost:8000/health", timeout=5)
        health.raise_for_status()
        print("\n✓ Backend is running")
        print(f"  Status: {health.json()}")
    except Exception as e:
        print(f"\n✗ Backend not running: {e}")
        return

    # Try to get runs
    try:
        runs_resp = requests.get(f"{BASE_URL}/runs", timeout=5)
        if runs_resp.status_code == 200:
            runs = runs_resp.json()
            print(f"\nTotal Runs: {len(runs)}")
            for i, run in enumerate(runs[:5], 1):
                print(f"  {i}. Run: {run.get('run_id', 'N/A')[:16]}... - Agent: {run.get('agent_name', 'N/A')}")
        else:
            print(f"\nRuns endpoint returned: {runs_resp.status_code}")
    except Exception as e:
        print(f"\n✗ Could not fetch runs: {e}")

    # Try to get agents
    try:
        agents_resp = requests.get(f"{BASE_URL}/agents", timeout=5)
        if agents_resp.status_code == 200:
            agents = agents_resp.json()
            print(f"\nTotal Agents: {len(agents)}")
            for i, agent in enumerate(agents[:5], 1):
                print(f"  {i}. Agent: {agent.get('agent_name', 'N/A')}")
        else:
            print(f"\nAgents endpoint returned: {agents_resp.status_code}")
    except Exception as e:
        print(f"\n✗ Could not fetch agents: {e}")

    # Try to get metrics/events count
    try:
        metrics_resp = requests.get(f"{BASE_URL}/metrics", timeout=5)
        if metrics_resp.status_code == 200:
            metrics = metrics_resp.json()
            print(f"\nMetrics:")
            print(json.dumps(metrics, indent=2))
        else:
            print(f"\nMetrics endpoint returned: {metrics_resp.status_code}")
    except Exception as e:
        print(f"\n✗ Could not fetch metrics: {e}")

    # Try direct database connection via psycopg2
    print("\n" + "-" * 80)
    print("Attempting direct database query...")
    print("-" * 80)
    try:
        import psycopg2
        import os
        from dotenv import load_dotenv

        load_dotenv()

        # Get connection params from environment
        conn = psycopg2.connect(
            host="localhost",
            port=5434,
            database="gati_db",
            user="gati_user",
            password="gati_password"
        )

        cursor = conn.cursor()

        # Count total events
        cursor.execute("SELECT COUNT(*) FROM events")
        total_events = cursor.fetchone()[0]
        print(f"\nTotal Events: {total_events}")

        # Count by event type
        cursor.execute("""
            SELECT event_type, COUNT(*) as count
            FROM events
            GROUP BY event_type
            ORDER BY count DESC
        """)
        print("\nEvents by Type:")
        event_types = cursor.fetchall()
        for event_type, count in event_types:
            print(f"  {event_type:20s}: {count:3d}")

        # Count runs
        cursor.execute("SELECT COUNT(DISTINCT run_id) FROM runs")
        total_runs = cursor.fetchone()[0]
        print(f"\nTotal Unique Runs: {total_runs}")

        # Count agents
        cursor.execute("SELECT COUNT(*) FROM agents")
        total_agents = cursor.fetchone()[0]
        print(f"Total Agents: {total_agents}")

        # Get latest events
        cursor.execute("""
            SELECT event_type, run_id, timestamp, data
            FROM events
            ORDER BY timestamp DESC
            LIMIT 10
        """)
        latest_events = cursor.fetchall()
        print("\nLatest 10 Events:")
        for i, (event_type, run_id, timestamp, data) in enumerate(latest_events, 1):
            status = data.get('status', 'N/A') if isinstance(data, dict) else 'N/A'
            print(f"  {i:2d}. [{event_type:15s}] {run_id[:8]}... - {timestamp}")

        cursor.close()
        conn.close()

        print("\n" + "=" * 80)
        print("Expected Events for Demo (3 graph executions):")
        print("  - 3 x AgentStartEvent (LangGraph start)")
        print("  - 3 x Tool calls (simulated_research)")
        print("  - 3 x LLM calls (summarizer_chain)")
        print("  - 3 x AgentEndEvent (LangGraph end)")
        print("  - 6 x NodeExecutionEvent (research + summarize nodes)")
        print("  - TOTAL: 18 events")
        print("=" * 80)

        if total_events == 18:
            print("\n✓ ✓ ✓ SUCCESS! All 18 events are in the database! ✓ ✓ ✓")
        else:
            print(f"\n⚠ Warning: Expected 18 events but found {total_events}")

    except ImportError:
        print("\n✗ psycopg2 not installed. Run: pip install psycopg2-binary")
    except Exception as e:
        print(f"\n✗ Database connection failed: {e}")
        print("  Make sure PostgreSQL is running on localhost:5434")

if __name__ == "__main__":
    check_events()
