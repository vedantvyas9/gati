"""Runs API endpoints for querying run information."""
import logging
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database.connection import get_async_session
from app.models import Run, Event
from app.schemas import (
    RunDetailResponse,
    RunTimelineResponse,
    RunTimelineEvent,
    ExecutionTraceResponse,
    ExecutionTreeNodeResponse,
    RunUpdateRequest,
)
from app.utils.timezone import format_datetime_local

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/runs/{agent_name}/{run_name}", response_model=RunDetailResponse)
async def get_run_details(
    agent_name: str,
    run_name: str,
    session: AsyncSession = Depends(get_async_session),
) -> RunDetailResponse:
    """
    Get full run details.

    Returns detailed information about a specific run including:
    - Run metadata and statistics
    - Associated agent
    - Number of events generated
    """
    try:
        # Get run with eager loaded events
        stmt = (
            select(Run)
            .where(Run.agent_name == agent_name, Run.run_name == run_name)
            .options(joinedload(Run.events))
        )
        result = await session.execute(stmt)
        run = result.unique().scalar_one_or_none()

        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run '{run_name}' for agent '{agent_name}' not found",
            )

        return RunDetailResponse(
            run_name=run.run_name,
            agent_name=run.agent_name,
            environment=run.environment,
            status=run.status,
            total_duration_ms=run.total_duration_ms or 0,
            total_cost=run.total_cost,
            tokens_in=run.tokens_in,
            tokens_out=run.tokens_out,
            metadata=run.run_metadata,
            created_at=format_datetime_local(run.created_at),
            event_count=len(run.events) if run.events else 0,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting run details: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get run details",
        ) from e


@router.get("/runs/{agent_name}/{run_name}/timeline", response_model=RunTimelineResponse)
async def get_run_timeline(
    agent_name: str,
    run_name: str,
    session: AsyncSession = Depends(get_async_session),
) -> RunTimelineResponse:
    """
    Get run timeline with events in chronological order.

    Returns all events for a specific run ordered by timestamp (oldest first),
    providing a chronological view of the run's execution.
    """
    try:
        # Get run
        run_stmt = select(Run).where(Run.agent_name == agent_name, Run.run_name == run_name)
        run_result = await session.execute(run_stmt)
        run = run_result.scalar_one_or_none()

        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run '{run_name}' for agent '{agent_name}' not found",
            )

        # Get events in chronological order
        events_stmt = (
            select(Event)
            .where(Event.run_id == run.run_id)
            .order_by(Event.timestamp.asc())
        )
        events_result = await session.execute(events_stmt)
        events = events_result.scalars().all()

        timeline_events = [
            RunTimelineEvent(
                event_id=event.event_id,
                event_type=event.event_type,
                timestamp=format_datetime_local(event.timestamp),
                data=event.data,
            )
            for event in events
        ]

        return RunTimelineResponse(
            run_name=run.run_name,
            agent_name=run.agent_name,
            status=run.status,
            total_duration_ms=run.total_duration_ms,
            created_at=format_datetime_local(run.created_at),
            events=timeline_events,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting run timeline: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get run timeline",
        ) from e


@router.get("/runs/{agent_name}/{run_name}/trace", response_model=ExecutionTraceResponse)
async def get_execution_trace(
    agent_name: str,
    run_name: str,
    session: AsyncSession = Depends(get_async_session),
) -> ExecutionTraceResponse:
    """
    Get execution trace with hierarchical event tree.

    Returns a tree-structured view of events for a run, showing parent-child
    relationships for a better understanding of the execution flow.
    """
    try:
        # Get run
        run_stmt = select(Run).where(Run.agent_name == agent_name, Run.run_name == run_name)
        run_result = await session.execute(run_stmt)
        run = run_result.scalar_one_or_none()

        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run '{run_name}' for agent '{agent_name}' not found",
            )

        # Get all events for the run
        events_stmt = (
            select(Event)
            .where(Event.run_id == run.run_id)
            .order_by(Event.timestamp.asc())
        )
        events_result = await session.execute(events_stmt)
        events = events_result.scalars().all()

        # Build tree structure using both parent_event_id (hierarchy) and previous_event_id (sequence)
        event_map: Dict[str, ExecutionTreeNodeResponse] = {}
        root_nodes: List[ExecutionTreeNodeResponse] = []
        node_to_previous: Dict[str, str] = {}  # Map event_id -> previous_event_id

        # First pass: create all nodes
        for event in events:
            node = ExecutionTreeNodeResponse(
                event_id=event.event_id,
                event_type=event.event_type,
                timestamp=format_datetime_local(event.timestamp),
                data=event.data,
                parent_event_id=event.parent_event_id,
                previous_event_id=event.previous_event_id,
                latency_ms=event.data.get("latency_ms"),
                cost=event.data.get("cost"),
                tokens_in=event.data.get("tokens_in"),
                tokens_out=event.data.get("tokens_out"),
            )
            event_map[event.event_id] = node
            if event.previous_event_id:
                node_to_previous[event.event_id] = event.previous_event_id

        # Second pass: build parent-child hierarchy
        # Special case: agent_end should NEVER be a child, always a root node
        root_node_ids = set()  # Track which nodes are already in root_nodes to avoid duplicates
        
        for event in events:
            node = event_map[event.event_id]
            # Agent End should always be a root node, never a child
            if event.event_type == 'agent_end':
                # Ensure agent_end is not in any parent's children list
                # Remove it from any parent's children if it was added earlier
                if event.parent_event_id and event.parent_event_id in event_map:
                    parent_node = event_map[event.parent_event_id]
                    # Remove from parent's children if present
                    parent_node.children = [child for child in parent_node.children if child.event_id != node.event_id]
                # Add to root_nodes only if not already added
                if node.event_id not in root_node_ids:
                    root_nodes.append(node)
                    root_node_ids.add(node.event_id)
            elif event.parent_event_id and event.parent_event_id in event_map:
                # Add to parent's children (but not if parent is agent_end)
                parent_node = event_map[event.parent_event_id]
                # Don't add children to agent_end - it should be a leaf node
                # Also don't add agent_end as a child
                if parent_node.event_type != 'agent_end' and node.event_type != 'agent_end':
                    parent_node.children.append(node)
            else:
                # Root node (no parent)
                if node.event_id not in root_node_ids:
                    root_nodes.append(node)
                    root_node_ids.add(node.event_id)

        # Third pass: restructure sequential flow using previous_event_id
        # Remove nodes from root_nodes if they have a previous_event_id pointing to another root
        # and append them as sequential siblings
        sequential_roots: List[ExecutionTreeNodeResponse] = []
        processed_ids = set()
        
        # Find agent_start first
        agent_start_node = None
        agent_end_node = None
        other_roots: List[ExecutionTreeNodeResponse] = []
        
        for root in root_nodes:
            if root.event_type == 'agent_start':
                agent_start_node = root
            elif root.event_type == 'agent_end':
                agent_end_node = root
            else:
                other_roots.append(root)
        
        # Build sequential chain starting from agent_start
        if agent_start_node:
            sequential_roots.append(agent_start_node)
            processed_ids.add(agent_start_node.event_id)
            
            # Follow the chain of previous_event_id
            current_id = agent_start_node.event_id
            while True:
                # Find next node in sequence (node whose previous_event_id == current_id)
                next_node = None
                for root in other_roots:
                    if root.previous_event_id == current_id and root.event_id not in processed_ids:
                        next_node = root
                        break
                
                if next_node:
                    sequential_roots.append(next_node)
                    processed_ids.add(next_node.event_id)
                    current_id = next_node.event_id
                else:
                    break
        
        # Add remaining roots that weren't part of the sequential chain
        for root in other_roots:
            if root.event_id not in processed_ids:
                sequential_roots.append(root)
        
        # Always ensure agent_end is at the end
        # If agent_end is already in sequential_roots, remove it and add it at the end
        # If agent_end is not in sequential_roots, add it at the end
        if agent_end_node:
            # Remove agent_end from sequential_roots if it's already there
            sequential_roots = [root for root in sequential_roots if root.event_id != agent_end_node.event_id]
            # Add agent_end at the end
            sequential_roots.append(agent_end_node)
        
        root_nodes = sequential_roots

        # Extract graph_structure from agent_start event and execution_flow from agent_end event
        graph_structure = None
        execution_flow = None

        for event in events:
            if event.event_type == "agent_start":
                # Check both in metadata and directly in data
                metadata = event.data.get("metadata", {})
                if metadata and isinstance(metadata, dict):
                    graph_structure = metadata.get("graph_structure")
                # Also check directly in event.data (new location)
                if not graph_structure:
                    graph_structure = event.data.get("graph_structure")
            elif event.event_type == "agent_end":
                # Check both in metadata and directly in data
                execution_flow = event.data.get("execution_flow")
                # Also check in metadata for backward compatibility
                if not execution_flow:
                    metadata = event.data.get("metadata", {})
                    if metadata and isinstance(metadata, dict):
                        execution_flow = metadata.get("execution_flow")
                # Also extract graph_structure from agent_end for correlation
                if not graph_structure:
                    graph_structure = event.data.get("graph_structure")

        return ExecutionTraceResponse(
            run_name=run.run_name,
            agent_name=run.agent_name,
            total_cost=run.total_cost,
            total_duration_ms=run.total_duration_ms or 0,
            total_tokens_in=run.tokens_in,
            total_tokens_out=run.tokens_out,
            execution_tree=root_nodes,
            graph_structure=graph_structure,
            execution_flow=execution_flow,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting execution trace: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get execution trace",
        ) from e


@router.delete("/runs/{agent_name}/{run_name}")
async def delete_run(
    agent_name: str,
    run_name: str,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """
    Delete a run and all associated events.

    Deletes the run and all events belonging to it.
    """
    try:
        # Verify run exists
        run_stmt = select(Run).where(Run.agent_name == agent_name, Run.run_name == run_name)
        run_result = await session.execute(run_stmt)
        run = run_result.scalar_one_or_none()

        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run '{run_name}' for agent '{agent_name}' not found",
            )

        # Delete all events for this run (cascade should handle this, but explicit is better)
        delete_events_stmt = sql_delete(Event).where(
            Event.run_id == run.run_id
        )
        await session.execute(delete_events_stmt)

        # Delete the run
        delete_run_stmt = sql_delete(Run).where(
            Run.agent_name == agent_name,
            Run.run_name == run_name
        )
        await session.execute(delete_run_stmt)

        await session.commit()

        return {
            "status": "success",
            "message": f"Run '{run_name}' for agent '{agent_name}' and all associated events deleted",
        }

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Error deleting run: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete run",
        ) from e


@router.patch("/runs/{agent_name}/{run_name}")
async def update_run_name(
    agent_name: str,
    run_name: str,
    update_request: RunUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
) -> RunDetailResponse:
    """
    Update a run's name.

    Allows editing of run names from the dashboard UI.
    Validates that the new name doesn't already exist for the agent.
    """
    try:
        # Check if run exists
        stmt = select(Run).where(
            Run.agent_name == agent_name,
            Run.run_name == run_name
        ).options(joinedload(Run.events))
        result = await session.execute(stmt)
        run = result.unique().scalar_one_or_none()

        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run '{run_name}' for agent '{agent_name}' not found",
            )

        # Check if new name already exists
        check_stmt = select(Run).where(
            Run.agent_name == agent_name,
            Run.run_name == update_request.new_run_name
        )
        check_result = await session.execute(check_stmt)
        existing_run = check_result.scalar_one_or_none()

        if existing_run:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Run name '{update_request.new_run_name}' already exists for agent '{agent_name}'",
            )

        # Update run name
        run.run_name = update_request.new_run_name
        await session.commit()
        await session.refresh(run)

        return RunDetailResponse(
            run_name=run.run_name,
            agent_name=run.agent_name,
            environment=run.environment,
            status=run.status,
            total_duration_ms=run.total_duration_ms or 0,
            total_cost=run.total_cost,
            tokens_in=run.tokens_in,
            tokens_out=run.tokens_out,
            metadata=run.run_metadata,
            created_at=format_datetime_local(run.created_at),
            event_count=len(run.events) if run.events else 0,
        )

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Error updating run name: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update run name",
        ) from e
