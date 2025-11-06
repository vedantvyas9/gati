"""Agents API endpoints for querying agent information."""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database.connection import get_async_session
from app.models import Agent, Run, Event
from app.schemas import AgentResponse, AgentStatsResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/agents", response_model=List[AgentResponse])
async def list_agents(
    session: AsyncSession = Depends(get_async_session),
) -> List[AgentResponse]:
    """
    List all agents.

    Returns a list of all registered agents.
    """
    try:
        stmt = select(Agent).order_by(Agent.created_at.desc())
        result = await session.execute(stmt)
        agents = result.scalars().all()

        return [
            AgentResponse(
                name=agent.name,
                description=agent.description,
                created_at=agent.created_at.isoformat(),
            )
            for agent in agents
        ]
    except Exception as e:
        logger.error(f"Error listing agents: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list agents",
        ) from e


@router.get("/agents/{agent_name}", response_model=AgentStatsResponse)
async def get_agent_stats(
    agent_name: str,
    session: AsyncSession = Depends(get_async_session),
) -> AgentStatsResponse:
    """
    Get agent details with statistics.

    Returns agent information along with aggregated metrics:
    - Total runs executed
    - Total events generated
    - Total cost
    - Average cost per run
    """
    try:
        # Get agent
        stmt = select(Agent).where(Agent.name == agent_name)
        result = await session.execute(stmt)
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_name}' not found",
            )

        # Get run statistics
        runs_stmt = select(
            func.count(Run.run_name).label("total_runs"),
            func.coalesce(func.sum(Run.total_cost), 0).label("total_cost"),
        ).where(Run.agent_name == agent_name)

        runs_result = await session.execute(runs_stmt)
        runs_row = runs_result.one()
        total_runs = runs_row.total_runs or 0
        total_cost = float(runs_row.total_cost or 0)

        # Get event count
        events_stmt = select(func.count(Event.event_id)).where(
            Event.agent_name == agent_name
        )
        events_result = await session.execute(events_stmt)
        total_events = events_result.scalar() or 0

        # Calculate average cost
        avg_cost = total_cost / total_runs if total_runs > 0 else 0.0

        return AgentStatsResponse(
            name=agent.name,
            description=agent.description,
            total_runs=total_runs,
            total_events=total_events,
            total_cost=total_cost,
            avg_cost=avg_cost,
            created_at=agent.created_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get agent statistics",
        ) from e


@router.get("/agents/{agent_name}/runs", response_model=List[dict])
async def get_agent_runs(
    agent_name: str,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
) -> List[dict]:
    """
    Get runs for a specific agent.

    Returns paginated list of runs for the specified agent,
    ordered by creation time (newest first).

    Query Parameters:
    - limit: Maximum number of runs to return (default: 50, max: 1000)
    - offset: Number of runs to skip (default: 0)
    """
    if limit > 1000:
        limit = 1000
    if offset < 0:
        offset = 0

    try:
        # Verify agent exists
        agent_stmt = select(Agent).where(Agent.name == agent_name)
        agent_result = await session.execute(agent_stmt)
        if not agent_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_name}' not found",
            )

        # Get runs
        stmt = (
            select(Run)
            .where(Run.agent_name == agent_name)
            .order_by(Run.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        runs = result.scalars().all()

        return [
            {
                "run_name": run.run_name,
                "agent_name": run.agent_name,
                "environment": run.environment,
                "status": run.status,
                "total_duration_ms": run.total_duration_ms or 0,
                "total_cost": run.total_cost,
                "tokens_in": run.tokens_in,
                "tokens_out": run.tokens_out,
                "created_at": run.created_at.isoformat(),
            }
            for run in runs
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent runs: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get agent runs",
        ) from e


@router.delete("/agents/{agent_name}")
async def delete_agent(
    agent_name: str,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """
    Delete an agent and all associated runs and events.

    Deletes the agent and cascades to delete all associated runs and events.
    """
    try:
        # Verify agent exists
        agent_stmt = select(Agent).where(Agent.name == agent_name)
        agent_result = await session.execute(agent_stmt)
        agent = agent_result.scalar_one_or_none()

        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_name}' not found",
            )

        # Delete all events for this agent (cascade should handle this, but explicit is better)
        delete_events_stmt = sql_delete(Event).where(
            Event.agent_name == agent_name
        )
        await session.execute(delete_events_stmt)

        # Delete all runs for this agent
        delete_runs_stmt = sql_delete(Run).where(Run.agent_name == agent_name)
        await session.execute(delete_runs_stmt)

        # Delete the agent
        delete_agent_stmt = sql_delete(Agent).where(Agent.name == agent_name)
        await session.execute(delete_agent_stmt)

        await session.commit()

        return {
            "status": "success",
            "message": f"Agent '{agent_name}' and all associated data deleted",
        }

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Error deleting agent: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete agent",
        ) from e
