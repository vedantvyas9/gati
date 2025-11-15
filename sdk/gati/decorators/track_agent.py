"""Decorator for tracking entire agent runs."""
import functools
import time
import inspect
from typing import Any, Callable, Dict, Optional

from gati.core.event import AgentStartEvent, AgentEndEvent, generate_run_id, generate_run_name
from gati.core.context import RunContextManager, get_current_run_id, get_current_run_name, set_parent_event_id
from gati.observe import observe

# Import serialization helpers from track_tool
from gati.decorators.track_tool import _serialize_value, _serialize_args_kwargs


def _track_sync_agent(
    func: Callable,
    agent_name: Optional[str] = None,
    *args: Any,
    **kwargs: Any
) -> Any:
    """Track a synchronous agent run.

    Args:
        func: Agent function being called
        agent_name: Optional custom name for the agent
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Function result
    """
    # Get agent name
    name = agent_name or func.__name__

    # Generate run_id and run_name
    run_id = generate_run_id(agent_name=name)
    run_name = generate_run_name(agent_name=name)

    # Serialize input
    try:
        input_data = _serialize_args_kwargs(args, kwargs, func)
    except Exception:
        input_data = {"error": "Failed to serialize input"}

    # Track start time
    start_time = time.time()
    error = None
    output_data = {}
    total_cost = 0.0

    # Create AgentStartEvent
    start_event_id = None
    try:
        start_event = AgentStartEvent(
            run_id=run_id,
            run_name=run_name,
            agent_name=name,
            input=input_data,
            metadata={},
        )
        start_event_id = start_event.event_id

        # Track start event
        try:
            observe.track_event(start_event)
        except Exception:
            pass
    except Exception:
        pass

    # Enter run context with both run_id and run_name
    with RunContextManager.run_context(run_id=run_id, run_name=run_name, agent_name=name):
        # Set this agent_start event as parent for all child events
        if start_event_id:
            set_parent_event_id(start_event_id)

        try:
            # Execute agent function
            result = func(*args, **kwargs)

            # Serialize output
            try:
                output_data = _serialize_value(result)
            except Exception:
                output_data = {"error": "Failed to serialize output"}

            return result

        except Exception as e:
            # Capture error
            error = {
                "type": type(e).__name__,
                "message": str(e),
            }
            output_data = {"error": error}
            raise

        finally:
            # Calculate total duration
            total_duration_ms = (time.time() - start_time) * 1000

            # TODO: Aggregate cost from events in buffer
            # For now, we'll track cost as 0.0
            # In a full implementation, you'd query the buffer for all events
            # in this run_name and sum their costs

            # Create AgentEndEvent
            try:
                end_event = AgentEndEvent(
                    run_id=run_id,
                    run_name=run_name,
                    agent_name=name,
                    output=output_data,
                    total_duration_ms=total_duration_ms,
                    total_cost=total_cost,
                )

                # Add error if present
                if error:
                    end_event.data["error"] = error

                # Track end event
                try:
                    observe.track_event(end_event)
                except Exception:
                    pass
            except Exception:
                pass


async def _track_async_agent(
    func: Callable,
    agent_name: Optional[str] = None,
    *args: Any,
    **kwargs: Any
) -> Any:
    """Track an asynchronous agent run.

    Args:
        func: Async agent function being called
        agent_name: Optional custom name for the agent
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Function result
    """
    # Get agent name
    name = agent_name or func.__name__

    # Generate run_id and run_name
    run_id = generate_run_id(agent_name=name)
    run_name = generate_run_name(agent_name=name)

    # Serialize input
    try:
        input_data = _serialize_args_kwargs(args, kwargs, func)
    except Exception:
        input_data = {"error": "Failed to serialize input"}

    # Track start time
    start_time = time.time()
    error = None
    output_data = {}
    total_cost = 0.0

    # Create AgentStartEvent
    start_event_id = None
    try:
        start_event = AgentStartEvent(
            run_id=run_id,
            run_name=run_name,
            agent_name=name,
            input=input_data,
            metadata={},
        )
        start_event_id = start_event.event_id

        # Track start event
        try:
            observe.track_event(start_event)
        except Exception:
            pass
    except Exception:
        pass

    # Enter run context with both run_id and run_name
    with RunContextManager.run_context(run_id=run_id, run_name=run_name, agent_name=name):
        # Set this agent_start event as parent for all child events
        if start_event_id:
            set_parent_event_id(start_event_id)

        try:
            # Execute async agent function
            result = await func(*args, **kwargs)

            # Serialize output
            try:
                output_data = _serialize_value(result)
            except Exception:
                output_data = {"error": "Failed to serialize output"}

            return result

        except Exception as e:
            # Capture error
            error = {
                "type": type(e).__name__,
                "message": str(e),
            }
            output_data = {"error": error}
            raise

        finally:
            # Calculate total duration
            total_duration_ms = (time.time() - start_time) * 1000

            # TODO: Aggregate cost from events in buffer
            # For now, we'll track cost as 0.0
            # In a full implementation, you'd query the buffer for all events
            # in this run_name and sum their costs

            # Create AgentEndEvent
            try:
                end_event = AgentEndEvent(
                    run_id=run_id,
                    run_name=run_name,
                    agent_name=name,
                    output=output_data,
                    total_duration_ms=total_duration_ms,
                    total_cost=total_cost,
                )

                # Add error if present
                if error:
                    end_event.data["error"] = error

                # Track end event
                try:
                    observe.track_event(end_event)
                except Exception:
                    pass
            except Exception:
                pass


def track_agent(name: Optional[str] = None):
    """Decorator for tracking entire agent runs.
    
    Creates AgentStartEvent at beginning, AgentEndEvent at end.
    Generates run_id and sets it in context.
    Tracks total duration and aggregates cost.
    Captures final output and handles errors.
    
    Args:
        name: Optional custom name for the agent (defaults to function name)
        
    Example:
        >>> @track_agent
        ... def my_agent(prompt: str):
        ...     # Agent logic here
        ...     return result
        
        >>> @track_agent(name="custom_agent")
        ... def my_agent(prompt: str):
        ...     # Agent logic here
        ...     return result
    """
    # Handle case where decorator is used without parentheses: @track_agent
    if callable(name):
        func = name
        agent_name = None
        
        # Check if function is async
        is_async = inspect.iscoroutinefunction(func)
        
        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await _track_async_agent(func, agent_name, *args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                return _track_sync_agent(func, agent_name, *args, **kwargs)
            return sync_wrapper
    
    # Used as @track_agent() or @track_agent(name="...")
    def decorator(func: Callable) -> Callable:
        # Check if function is async
        is_async = inspect.iscoroutinefunction(func)
        
        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await _track_async_agent(func, name, *args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                return _track_sync_agent(func, name, *args, **kwargs)
            return sync_wrapper
    
    return decorator













