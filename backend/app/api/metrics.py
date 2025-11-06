"""Metrics aggregation API endpoints."""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_async_session
from app.models import Agent, Run, Event
from app.schemas import (
    AgentMetricsResponse,
    GlobalMetricsResponse,
    TopAgentByCost,
    TopAgentByRuns,
    CostTimestampData,
    TokensTimestampData,
    AgentComparisonData,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/metrics/summary", response_model=GlobalMetricsResponse)
async def get_metrics_summary(
    session: AsyncSession = Depends(get_async_session),
) -> GlobalMetricsResponse:
    """
    Get global metrics summary across all agents.

    Returns aggregated metrics including:
    - Total agents, runs, events
    - Cost statistics
    - Token usage
    - Duration metrics
    - Top agents by cost and runs
    """
    try:
        # Total agents
        agents_stmt = select(func.count(Agent.name))
        agents_result = await session.execute(agents_stmt)
        total_agents = agents_result.scalar() or 0

        # Total runs and cost metrics
        runs_stmt = select(
            func.count(Run.run_id).label("total_runs"),
            func.coalesce(func.sum(Run.total_cost), 0).label("total_cost"),
            func.coalesce(func.sum(Run.tokens_in), 0).label("total_tokens_in"),
            func.coalesce(func.sum(Run.tokens_out), 0).label("total_tokens_out"),
            func.coalesce(func.sum(Run.total_duration_ms), 0).label("total_duration_ms"),
        )
        runs_result = await session.execute(runs_stmt)
        runs_row = runs_result.one()

        total_runs = runs_row.total_runs or 0
        total_cost = float(runs_row.total_cost or 0)
        total_tokens_in = float(runs_row.total_tokens_in or 0)
        total_tokens_out = float(runs_row.total_tokens_out or 0)
        total_duration_ms = float(runs_row.total_duration_ms or 0)

        # Total events
        events_stmt = select(func.count(Event.event_id))
        events_result = await session.execute(events_stmt)
        total_events = events_result.scalar() or 0

        # Calculate averages
        avg_cost_per_run = total_cost / total_runs if total_runs > 0 else 0.0
        avg_tokens_in_per_run = total_tokens_in / total_runs if total_runs > 0 else 0.0
        avg_tokens_out_per_run = total_tokens_out / total_runs if total_runs > 0 else 0.0
        total_duration_hours = total_duration_ms / (1000 * 60 * 60)

        # Top agents by cost
        top_cost_stmt = (
            select(
                Run.agent_name,
                func.coalesce(func.sum(Run.total_cost), 0).label("cost"),
            )
            .group_by(Run.agent_name)
            .order_by(func.sum(Run.total_cost).desc())
            .limit(5)
        )
        top_cost_result = await session.execute(top_cost_stmt)
        top_agents_by_cost = [
            TopAgentByCost(agent_name=row[0], cost=float(row[1]))
            for row in top_cost_result.all()
        ]

        # Top agents by runs
        top_runs_stmt = (
            select(
                Run.agent_name,
                func.count(Run.run_id).label("runs"),
            )
            .group_by(Run.agent_name)
            .order_by(func.count(Run.run_id).desc())
            .limit(5)
        )
        top_runs_result = await session.execute(top_runs_stmt)
        top_agents_by_runs = [
            TopAgentByRuns(agent_name=row[0], runs=int(row[1]))
            for row in top_runs_result.all()
        ]

        return GlobalMetricsResponse(
            total_agents=total_agents,
            total_runs=total_runs,
            total_events=total_events,
            total_cost=total_cost,
            avg_cost_per_run=avg_cost_per_run,
            avg_tokens_in_per_run=avg_tokens_in_per_run,
            avg_tokens_out_per_run=avg_tokens_out_per_run,
            total_tokens_in=total_tokens_in,
            total_tokens_out=total_tokens_out,
            total_duration_hours=total_duration_hours,
            top_agents_by_cost=top_agents_by_cost,
            top_agents_by_runs=top_agents_by_runs,
        )

    except Exception as e:
        logger.error(f"Error getting metrics summary: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get metrics summary",
        ) from e


@router.get("/agents/{agent_name}/metrics", response_model=AgentMetricsResponse)
async def get_agent_metrics(
    agent_name: str,
    session: AsyncSession = Depends(get_async_session),
) -> AgentMetricsResponse:
    """
    Get aggregated metrics for a specific agent.

    Returns per-agent statistics including:
    - Run counts and costs
    - Token usage
    - Average duration
    """
    try:
        # Verify agent exists
        agent_stmt = select(Agent).where(Agent.name == agent_name)
        agent_result = await session.execute(agent_stmt)
        if not agent_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_name}' not found",
            )

        # Get run metrics
        runs_stmt = select(
            func.count(Run.run_id).label("total_runs"),
            func.coalesce(func.sum(Run.total_cost), 0).label("total_cost"),
            func.coalesce(func.avg(Run.total_cost), 0).label("avg_cost"),
            func.coalesce(func.sum(Run.tokens_in), 0).label("total_tokens_in"),
            func.coalesce(func.avg(Run.tokens_in), 0).label("avg_tokens_in"),
            func.coalesce(func.sum(Run.tokens_out), 0).label("total_tokens_out"),
            func.coalesce(func.avg(Run.tokens_out), 0).label("avg_tokens_out"),
            func.coalesce(func.sum(Run.total_duration_ms), 0).label("total_duration"),
            func.coalesce(func.avg(Run.total_duration_ms), 0).label("avg_duration"),
        ).where(Run.agent_name == agent_name)

        runs_result = await session.execute(runs_stmt)
        runs_row = runs_result.one()

        # Get event count
        events_stmt = select(func.count(Event.event_id)).where(
            Event.agent_name == agent_name
        )
        events_result = await session.execute(events_stmt)
        total_events = events_result.scalar() or 0

        return AgentMetricsResponse(
            agent_name=agent_name,
            total_runs=runs_row.total_runs or 0,
            total_events=total_events,
            total_cost=float(runs_row.total_cost or 0),
            avg_cost_per_run=float(runs_row.avg_cost or 0),
            avg_tokens_in=float(runs_row.avg_tokens_in or 0),
            avg_tokens_out=float(runs_row.avg_tokens_out or 0),
            avg_duration_ms=float(runs_row.avg_duration or 0),
            total_tokens_in=float(runs_row.total_tokens_in or 0),
            total_tokens_out=float(runs_row.total_tokens_out or 0),
            total_duration_ms=float(runs_row.total_duration or 0),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent metrics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get agent metrics",
        ) from e


@router.get("/metrics/cost-timeline", response_model=List[CostTimestampData])
async def get_cost_timeline(
    days: int = Query(30, ge=1, le=365, description="Number of days to retrieve"),
    session: AsyncSession = Depends(get_async_session),
) -> List[CostTimestampData]:
    """
    Get cost timeline data for charting.

    Returns daily cost aggregation over the specified period with cumulative totals.
    """
    try:
        # Calculate start date
        start_date = datetime.utcnow() - timedelta(days=days)

        # Get daily cost data
        cost_stmt = (
            select(
                func.date(Run.created_at).label("date"),
                func.coalesce(func.sum(Run.total_cost), 0).label("daily_cost"),
            )
            .where(Run.created_at >= start_date)
            .group_by(func.date(Run.created_at))
            .order_by(func.date(Run.created_at).asc())
        )

        cost_result = await session.execute(cost_stmt)
        cost_rows = cost_result.all()

        # Build result with cumulative costs
        cumulative_cost = 0.0
        result: List[CostTimestampData] = []

        for row in cost_rows:
            daily_cost = float(row[1] or 0)
            cumulative_cost += daily_cost
            result.append(
                CostTimestampData(
                    timestamp=row[0].isoformat() if row[0] else "",
                    cost=daily_cost,
                    cumulative_cost=cumulative_cost,
                )
            )

        return result

    except Exception as e:
        logger.error(f"Error getting cost timeline: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get cost timeline",
        ) from e


@router.get("/metrics/tokens-timeline", response_model=List[TokensTimestampData])
async def get_tokens_timeline(
    days: int = Query(30, ge=1, le=365, description="Number of days to retrieve"),
    session: AsyncSession = Depends(get_async_session),
) -> List[TokensTimestampData]:
    """
    Get tokens timeline data for charting.

    Returns daily token usage aggregation over the specified period with cumulative totals.
    """
    try:
        # Calculate start date
        start_date = datetime.utcnow() - timedelta(days=days)

        # Get daily token data
        tokens_stmt = (
            select(
                func.date(Run.created_at).label("date"),
                func.coalesce(func.sum(Run.tokens_in), 0).label("daily_tokens_in"),
                func.coalesce(func.sum(Run.tokens_out), 0).label("daily_tokens_out"),
            )
            .where(Run.created_at >= start_date)
            .group_by(func.date(Run.created_at))
            .order_by(func.date(Run.created_at).asc())
        )

        tokens_result = await session.execute(tokens_stmt)
        tokens_rows = tokens_result.all()

        # Build result with cumulative tokens
        cumulative_tokens_in = 0.0
        cumulative_tokens_out = 0.0
        result: List[TokensTimestampData] = []

        for row in tokens_rows:
            daily_tokens_in = float(row[1] or 0)
            daily_tokens_out = float(row[2] or 0)
            cumulative_tokens_in += daily_tokens_in
            cumulative_tokens_out += daily_tokens_out

            result.append(
                TokensTimestampData(
                    timestamp=row[0].isoformat() if row[0] else "",
                    tokens_in=daily_tokens_in,
                    tokens_out=daily_tokens_out,
                    cumulative_tokens_in=cumulative_tokens_in,
                    cumulative_tokens_out=cumulative_tokens_out,
                )
            )

        return result

    except Exception as e:
        logger.error(f"Error getting tokens timeline: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get tokens timeline",
        ) from e


@router.get("/metrics/agents-comparison", response_model=List[AgentComparisonData])
async def get_agents_comparison(
    session: AsyncSession = Depends(get_async_session),
) -> List[AgentComparisonData]:
    """
    Get agent comparison data for charts.

    Returns aggregated metrics for each agent for comparison purposes.
    """
    try:
        # Get per-agent aggregated data
        agent_stmt = (
            select(
                Run.agent_name,
                func.count(Run.run_id).label("total_runs"),
                func.coalesce(func.sum(Run.total_cost), 0).label("total_cost"),
                func.coalesce(func.avg(Run.total_cost), 0).label("avg_cost"),
                func.coalesce(
                    func.sum(Run.tokens_in + Run.tokens_out), 0
                ).label("total_tokens"),
            )
            .group_by(Run.agent_name)
            .order_by(func.sum(Run.total_cost).desc())
        )

        agent_result = await session.execute(agent_stmt)
        agent_rows = agent_result.all()

        result: List[AgentComparisonData] = []
        for row in agent_rows:
            result.append(
                AgentComparisonData(
                    agent_name=row[0],
                    runs=int(row[1] or 0),
                    cost=float(row[2] or 0),
                    avg_cost_per_run=float(row[3] or 0),
                    total_tokens=float(row[4] or 0),
                )
            )

        return result

    except Exception as e:
        logger.error(f"Error getting agents comparison: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get agents comparison",
        ) from e
