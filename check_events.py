"""Check events in GATI database."""
import asyncio
import sys
sys.path.insert(0, 'backend')

from app.database.connection import init_async_db, close_async_db, _async_session_factory
from app.models import Event, Run, Agent
from sqlalchemy import select, func, distinct

async def check_events():
    """Check and display event counts."""
    # Initialize database
    await init_async_db()

    async with _async_session_factory() as session:
        # Count total events
        total_events_result = await session.execute(
            select(func.count()).select_from(Event)
        )
        total_events = total_events_result.scalar()

        # Count by event type
        event_types_result = await session.execute(
            select(Event.event_type, func.count(Event.id))
            .group_by(Event.event_type)
        )
        event_types = event_types_result.all()

        # Count runs
        runs_result = await session.execute(
            select(func.count(distinct(Run.run_id)))
        )
        total_runs = runs_result.scalar()

        # Count agents
        agents_result = await session.execute(
            select(func.count()).select_from(Agent)
        )
        total_agents = agents_result.scalar()

        # Get latest events
        latest_events_result = await session.execute(
            select(Event.event_type, Event.run_id, Event.timestamp, Event.data)
            .order_by(Event.timestamp.desc())
            .limit(10)
        )
        latest_events = latest_events_result.all()

        print("=" * 80)
        print("GATI Database Event Summary")
        print("=" * 80)
        print(f"\nTotal Events: {total_events}")
        print(f"Total Runs: {total_runs}")
        print(f"Total Agents: {total_agents}")

        print("\n" + "-" * 80)
        print("Events by Type:")
        print("-" * 80)
        for event_type, count in event_types:
            print(f"  {event_type:20s}: {count:3d}")

        print("\n" + "-" * 80)
        print("Latest 10 Events:")
        print("-" * 80)
        for i, (event_type, run_id, timestamp, data) in enumerate(latest_events, 1):
            status = data.get('status', 'N/A') if isinstance(data, dict) else 'N/A'
            print(f"  {i:2d}. [{event_type:15s}] {run_id[:8]}... - Status: {status}")

        print("\n" + "=" * 80)

        # Expected event breakdown for the demo
        print("\nExpected Events for Demo (3 graph executions):")
        print("  - 3 x AgentStartEvent (LangGraph start)")
        print("  - 3 x Tool calls (simulated_research)")
        print("  - 3 x LLM calls (summarizer_chain)")
        print("  - 3 x AgentEndEvent (LangGraph end)")
        print("  - 6 x NodeExecutionEvent (research + summarize nodes)")
        print("  - TOTAL: 18 events")
        print("=" * 80)

if __name__ == "__main__":
    try:
        asyncio.run(check_events())
    finally:
        # Cleanup
        asyncio.run(close_async_db())
