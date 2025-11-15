"""Decorator for tracking individual steps within an agent."""
import functools
import time
import inspect
from typing import Any, Callable, Dict, Optional

from gati.core.event import StepEvent
from gati.core.context import get_current_run_id
from gati.observe import observe

# Import serialization helpers from track_tool
from gati.decorators.track_tool import _serialize_value, _serialize_args_kwargs


def _track_sync_step(
    func: Callable,
    step_name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    *args: Any,
    **kwargs: Any
) -> Any:
    """Track a synchronous step execution.
    
    Args:
        func: Function being called
        step_name: Optional custom name for the step
        metadata: Optional metadata dictionary
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        Function result
    """
    # Get step name
    name = step_name or func.__name__
    
    # Get current run_id from context
    run_id = get_current_run_id()
    
    # Serialize input
    try:
        input_data = _serialize_args_kwargs(args, kwargs, func)
    except Exception:
        input_data = {"error": "Failed to serialize input"}
    
    # Track execution time
    start_time = time.time()
    error = None
    output_data = {}
    step_metadata = metadata or {}
    
    try:
        # Execute function
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
        # Calculate execution time
        duration_ms = (time.time() - start_time) * 1000
        
        # Create event
        try:
            event = StepEvent(
                run_id=run_id or "",
                step_name=name,
                input=input_data,
                output=output_data,
                duration_ms=duration_ms,
                metadata=step_metadata,
            )
            
            # Add error if present
            if error:
                event.data["error"] = error
            
            # Track event (gracefully handle if observe not initialized)
            try:
                observe.track_event(event)
            except Exception:
                # Silently fail if observe is not initialized
                pass
                
        except Exception:
            # Silently fail if event creation fails
            pass


async def _track_async_step(
    func: Callable,
    step_name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    *args: Any,
    **kwargs: Any
) -> Any:
    """Track an asynchronous step execution.
    
    Args:
        func: Async function being called
        step_name: Optional custom name for the step
        metadata: Optional metadata dictionary
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        Function result
    """
    # Get step name
    name = step_name or func.__name__
    
    # Get current run_id from context
    run_id = get_current_run_id()
    
    # Serialize input
    try:
        input_data = _serialize_args_kwargs(args, kwargs, func)
    except Exception:
        input_data = {"error": "Failed to serialize input"}
    
    # Track execution time
    start_time = time.time()
    error = None
    output_data = {}
    step_metadata = metadata or {}
    
    try:
        # Execute async function
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
        # Calculate execution time
        duration_ms = (time.time() - start_time) * 1000
        
        # Create event
        try:
            event = StepEvent(
                run_id=run_id or "",
                step_name=name,
                input=input_data,
                output=output_data,
                duration_ms=duration_ms,
                metadata=step_metadata,
            )
            
            # Add error if present
            if error:
                event.data["error"] = error
            
            # Track event (gracefully handle if observe not initialized)
            try:
                observe.track_event(event)
            except Exception:
                # Silently fail if observe is not initialized
                pass
                
        except Exception:
            # Silently fail if event creation fails
            pass


def track_step(name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
    """Decorator for tracking individual steps within an agent.
    
    Similar to @track_tool but for logical steps within an agent.
    Creates StepEvent (similar to ToolCallEvent).
    Uses current run_id from context.
    Captures duration and output.
    
    Args:
        name: Optional custom name for the step (defaults to function name)
        metadata: Optional metadata dictionary
        
    Example:
        >>> @track_step
        ... def my_step(input_data):
        ...     # Process input
        ...     return result
        
        >>> @track_step(name="custom_step", metadata={"version": "1.0"})
        ... def my_step(input_data):
        ...     # Process input
        ...     return result
    """
    # Handle case where decorator is used without parentheses: @track_step
    if callable(name):
        func = name
        step_name = None
        step_metadata = None
        
        # Check if function is async
        is_async = inspect.iscoroutinefunction(func)
        
        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await _track_async_step(func, step_name, step_metadata, *args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                return _track_sync_step(func, step_name, step_metadata, *args, **kwargs)
            return sync_wrapper
    
    # Used as @track_step() or @track_step(name="...", metadata={...})
    def decorator(func: Callable) -> Callable:
        # Check if function is async
        is_async = inspect.iscoroutinefunction(func)
        
        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await _track_async_step(func, name, metadata, *args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                return _track_sync_step(func, name, metadata, *args, **kwargs)
            return sync_wrapper
    
    return decorator













