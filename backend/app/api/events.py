"""Event ingestion API endpoint."""
import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.sqlite import insert

from app.config import get_settings
from app.database.connection import get_async_session
from app.models import Event, Run, Agent
from app.schemas import EventBatch, EventResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/events", status_code=status.HTTP_200_OK)
async def ingest_events(
    batch: EventBatch,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """
    Ingest batch of events from SDK.

    Accepts a batch of events and performs bulk insert into database.
    Automatically creates agents and runs as needed.

    Request body:
    ```json
    {
        "events": [
            {
                "event_type": "llm_call",
                "run_id": "123e4567-e89b-12d3-a456-426614174000",
                "agent_name": "my_agent",
                "timestamp": "2024-11-04T10:30:00Z",
                "data": {
                    "model": "gpt-4",
                    "tokens_in": 100,
                    "tokens_out": 50
                }
            }
        ]
    }
    ```

    Returns:
    ```json
    {
        "status": "success",
        "message": "Ingested 1 events",
        "count": 1,
        "failed": 0
    }
    ```
    """
    if not batch.events:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event batch cannot be empty",
        )

    try:
        # Collect unique agents and runs from events
        agents_set = set()
        runs_dict = {}  # key: (agent_name, run_id), value: (agent_name, run_name)

        for event in batch.events:
            agents_set.add(event.agent_name)
            run_key = (event.agent_name, event.run_id)
            if run_key not in runs_dict:
                runs_dict[run_key] = (event.agent_name, event.run_name)

        # Ensure agents exist (create if needed)
        await _ensure_agents_exist(session, agents_set)

        # Ensure runs exist (create if needed) - handles auto-increment of run names
        run_id_mapping = await _ensure_runs_exist(session, runs_dict)

        # Bulk insert events
        events_to_insert = []
        for event in batch.events:
            # Use provided event_id or generate a new one
            event_id = event.event_id if event.event_id else str(uuid.uuid4())

            # Parse timestamp
            try:
                ts = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                ts = datetime.utcnow()

            # Get the actual run_id (should be the same as provided)
            run_key = (event.agent_name, event.run_id)
            actual_run_id = run_id_mapping.get(run_key, event.run_id)

            events_to_insert.append({
                "event_id": event_id,
                "run_id": actual_run_id,
                "agent_name": event.agent_name,
                "event_type": event.event_type,
                "timestamp": ts,
                "parent_event_id": event.parent_event_id,  # Include parent_event_id
                "data": event.data,
            })

        # Perform bulk insert
        if events_to_insert:
            stmt = insert(Event).values(events_to_insert)
            # Use on_conflict_do_nothing for SQLite to handle potential duplicates
            stmt = stmt.on_conflict_do_nothing(index_elements=['event_id'])
            await session.execute(stmt)
            await session.commit()

            logger.info(f"Successfully ingested {len(events_to_insert)} events")

            # Aggregate metrics for affected runs
            await _aggregate_run_metrics(session, runs_dict, events_to_insert)

        return {
            "status": "success",
            "message": f"Ingested {len(events_to_insert)} events",
            "count": len(events_to_insert),
            "failed": 0,
        }

    except Exception as e:
        logger.error(f"Error ingesting events: {str(e)}", exc_info=True)
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest events: {str(e)}",
        ) from e


async def _ensure_agents_exist(
    session: AsyncSession,
    agent_names: set,
) -> None:
    """Create agents if they don't exist."""
    if not agent_names:
        return

    try:
        # Check which agents already exist
        stmt = select(Agent.name).where(Agent.name.in_(list(agent_names)))
        result = await session.execute(stmt)
        existing_agents = {row[0] for row in result.fetchall()}

        # Create missing agents
        missing_agents = agent_names - existing_agents
        if missing_agents:
            for agent_name in missing_agents:
                agent = Agent(name=agent_name, description=f"Auto-created agent: {agent_name}")
                session.add(agent)

            await session.commit()
            logger.info(f"Created {len(missing_agents)} new agents")

    except Exception as e:
        logger.error(f"Error ensuring agents exist: {str(e)}", exc_info=True)
        await session.rollback()
        raise


async def _ensure_runs_exist(
    session: AsyncSession,
    runs_dict: dict[tuple[str, str], tuple[str, str]],
) -> dict[tuple[str, str], str]:
    """Create runs if they don't exist.

    Args:
        runs_dict: Dictionary mapping (agent_name, run_id) -> (agent_name, run_name)

    Returns:
        Mapping of (agent_name, run_id) to actual run_id (same as input)
    """
    if not runs_dict:
        return {}

    run_id_mapping = {}

    try:
        # Group by agent to check existing runs
        agents_to_check = {agent_name for agent_name, _ in runs_dict.keys()}

        for agent_name in agents_to_check:
            # Get all run_ids for this agent from the batch
            agent_run_ids = [run_id for ag, run_id in runs_dict.keys() if ag == agent_name]

            # Check which runs already exist for this agent
            stmt = select(Run.run_id).where(
                Run.agent_name == agent_name,
                Run.run_id.in_(agent_run_ids)
            )
            result = await session.execute(stmt)
            existing_run_ids = {row[0] for row in result.fetchall()}

            # Get the highest run number for this agent for auto-increment
            stmt = select(Run.run_name).where(Run.agent_name == agent_name)
            result = await session.execute(stmt)
            all_run_names = [row[0] for row in result.fetchall()]

            # Extract run numbers and find max
            max_run_number = 0
            for name in all_run_names:
                if name.startswith("run "):
                    try:
                        num = int(name.split()[1])
                        max_run_number = max(max_run_number, num)
                    except (IndexError, ValueError):
                        pass

            # Create missing runs
            for ag, run_id in runs_dict.keys():
                if ag != agent_name:
                    continue

                run_key = (ag, run_id)
                agent_name_from_dict, run_name = runs_dict[run_key]

                if run_id not in existing_run_ids:
                    # Check if this is a temp name that needs auto-increment
                    if run_name.startswith("temp_"):
                        # Auto-assign next run number
                        max_run_number += 1
                        actual_run_name = f"run {max_run_number}"
                    else:
                        # Use the provided run name as-is
                        actual_run_name = run_name

                    # Create the run
                    run = Run(
                        run_id=run_id,
                        agent_name=agent_name,
                        run_name=actual_run_name,
                        status="active",
                    )
                    session.add(run)
                    run_id_mapping[run_key] = run_id
                else:
                    # Run already exists, use existing run_id
                    run_id_mapping[run_key] = run_id

        await session.commit()
        logger.info(f"Ensured {len(runs_dict)} runs exist")

        return run_id_mapping

    except Exception as e:
        logger.error(f"Error ensuring runs exist: {str(e)}", exc_info=True)
        await session.rollback()
        raise


async def _aggregate_run_metrics(
    session: AsyncSession,
    runs_dict: dict[tuple[str, str], tuple[str, str]],
    events_to_insert: list[dict],
) -> None:
    """Aggregate metrics from events and update Run model.

    For each run that received new events, calculate:
    - total_cost: sum of all event costs
    - tokens_in: sum of all event tokens_in
    - tokens_out: sum of all event tokens_out
    - total_duration_ms: max timestamp - min timestamp (or sum of latencies)

    Args:
        session: Database session
        runs_dict: Mapping of (agent_name, run_id) -> (agent_name, run_name)
        events_to_insert: List of event dictionaries that were inserted
    """
    if not runs_dict:
        return

    try:
        # Get unique run_ids from the inserted events
        run_ids_with_events = set()
        for event_dict in events_to_insert:
            run_ids_with_events.add(event_dict["run_id"])

        # For each affected run, aggregate metrics
        for run_id in run_ids_with_events:
            # Get all events for this run
            events_stmt = select(Event).where(Event.run_id == run_id)
            events_result = await session.execute(events_stmt)
            events = events_result.scalars().all()

            if not events:
                continue

            # Aggregate metrics
            total_cost = 0.0
            total_tokens_in = 0.0
            total_tokens_out = 0.0
            min_timestamp = None
            max_timestamp = None

            for event in events:
                # Extract metrics from event.data
                event_data = event.data or {}

                # Cost
                if "cost" in event_data and event_data["cost"] is not None:
                    try:
                        total_cost += float(event_data["cost"])
                    except (TypeError, ValueError):
                        pass

                # Tokens
                if "tokens_in" in event_data and event_data["tokens_in"] is not None:
                    try:
                        total_tokens_in += float(event_data["tokens_in"])
                    except (TypeError, ValueError):
                        pass

                if "tokens_out" in event_data and event_data["tokens_out"] is not None:
                    try:
                        total_tokens_out += float(event_data["tokens_out"])
                    except (TypeError, ValueError):
                        pass

                # Track timestamps for duration calculation
                if event.timestamp:
                    if min_timestamp is None or event.timestamp < min_timestamp:
                        min_timestamp = event.timestamp
                    if max_timestamp is None or event.timestamp > max_timestamp:
                        max_timestamp = event.timestamp

            # Calculate total duration in milliseconds
            total_duration_ms = None
            if min_timestamp and max_timestamp:
                duration = max_timestamp - min_timestamp
                total_duration_ms = duration.total_seconds() * 1000

            # Update the Run model
            run_stmt = select(Run).where(Run.run_id == run_id)
            run_result = await session.execute(run_stmt)
            run = run_result.scalar_one_or_none()

            if run:
                run.total_cost = total_cost
                run.tokens_in = total_tokens_in
                run.tokens_out = total_tokens_out
                if total_duration_ms is not None:
                    run.total_duration_ms = total_duration_ms
                session.add(run)

        await session.commit()
        logger.info(f"Aggregated metrics for {len(run_ids_with_events)} runs")

    except Exception as e:
        logger.error(f"Error aggregating run metrics: {str(e)}", exc_info=True)
        await session.rollback()
        # Don't raise - metrics aggregation failure shouldn't block event ingestion
