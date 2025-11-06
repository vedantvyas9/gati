"""Decorator for tracking custom function calls as tools."""
import functools
import time
import inspect
from typing import Any, Callable, Dict, Optional, Union

from gati.core.event import ToolCallEvent, generate_run_id, generate_run_name
from gati.core.context import get_current_run_id, get_current_run_name, get_parent_event_id
from gati.observe import observe


def _serialize_value(value: Any) -> Any:
    """Serialize a value to a JSON-serializable format.
    
    Args:
        value: Value to serialize
        
    Returns:
        Serialized value (dict, list, or primitive)
    """
    try:
        # Try to convert to dict if it has to_dict method
        if hasattr(value, 'to_dict'):
            return value.to_dict()
        
        # Try to convert to dict if it has __dict__
        if hasattr(value, '__dict__'):
            return {
                '__type__': type(value).__name__,
                '__module__': getattr(type(value), '__module__', 'unknown'),
                '__dict__': {k: _serialize_value(v) for k, v in value.__dict__.items()}
            }
        
        # Handle lists and tuples
        if isinstance(value, (list, tuple)):
            return [_serialize_value(item) for item in value]
        
        # Handle dictionaries
        if isinstance(value, dict):
            return {k: _serialize_value(v) for k, v in value.items()}
        
        # Try JSON serialization test
        import json
        json.dumps(value, default=str)
        return value
        
    except (TypeError, ValueError):
        # Fallback to string representation
        try:
            return str(value)
        except Exception:
            return "<non-serializable>"


def _serialize_args_kwargs(args: tuple, kwargs: dict, func: Callable) -> Dict[str, Any]:
    """Serialize function arguments to a dictionary.
    
    Args:
        args: Positional arguments
        kwargs: Keyword arguments
        func: Function being called
        
    Returns:
        Dictionary representation of arguments
    """
    try:
        # Get function signature
        sig = inspect.signature(func)
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()
        
        # Convert to dict and serialize
        result = {}
        for name, value in bound_args.arguments.items():
            result[name] = _serialize_value(value)
        
        return result
    except Exception:
        # Fallback: simple positional + keyword args
        return {
            "args": [_serialize_value(arg) for arg in args],
            "kwargs": {k: _serialize_value(v) for k, v in kwargs.items()}
        }


def _track_sync_tool(
    func: Callable,
    tool_name: Optional[str] = None,
    *args: Any,
    **kwargs: Any
) -> Any:
    """Track a synchronous tool call.
    
    Args:
        func: Function being called
        tool_name: Optional custom name for the tool
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        Function result
    """
    # Get tool name
    name = tool_name or func.__name__
    
    # Get current run_id and run_name from context
    run_id = get_current_run_id()
    run_name = get_current_run_name()
    
    # Serialize input
    try:
        input_data = _serialize_args_kwargs(args, kwargs, func)
    except Exception:
        input_data = {"error": "Failed to serialize input"}
    
    # Track execution time
    start_time = time.time()
    error = None
    output_data = {}
    
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
            # Get parent event ID from context
            parent_event_id = get_parent_event_id()

            event = ToolCallEvent(
                run_id=run_id or "",
                run_name=run_name or "",
                tool_name=name,
                input=input_data,
                output=output_data,
                latency_ms=duration_ms,
            )

            # Set parent event ID if available
            if parent_event_id:
                event.parent_event_id = parent_event_id

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


async def _track_async_tool(
    func: Callable,
    tool_name: Optional[str] = None,
    *args: Any,
    **kwargs: Any
) -> Any:
    """Track an asynchronous tool call.
    
    Args:
        func: Async function being called
        tool_name: Optional custom name for the tool
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        Function result
    """
    # Get tool name
    name = tool_name or func.__name__
    
    # Get current run_id and run_name from context
    run_id = get_current_run_id()
    run_name = get_current_run_name()
    
    # Serialize input
    try:
        input_data = _serialize_args_kwargs(args, kwargs, func)
    except Exception:
        input_data = {"error": "Failed to serialize input"}
    
    # Track execution time
    start_time = time.time()
    error = None
    output_data = {}
    
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
            # Get parent event ID from context
            parent_event_id = get_parent_event_id()

            event = ToolCallEvent(
                run_id=run_id or "",
                run_name=run_name or "",
                tool_name=name,
                input=input_data,
                output=output_data,
                latency_ms=duration_ms,
            )

            # Set parent event ID if available
            if parent_event_id:
                event.parent_event_id = parent_event_id

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


def track_tool(name: Optional[str] = None):
    """Decorator for tracking custom function calls as tools.
    
    Captures function name, input args, output, execution time, and errors.
    Creates a ToolCallEvent and sends it to the buffer.
    
    Args:
        name: Optional custom name for the tool (defaults to function name)
        
    Example:
        >>> @track_tool
        ... def my_api_call(query: str):
        ...     return requests.get(f"api.com?q={query}")
        
        >>> @track_tool(name="custom_api")
        ... def my_api_call(query: str):
        ...     return requests.get(f"api.com?q={query}")
    """
    # Handle case where decorator is used without parentheses: @track_tool
    if callable(name):
        func = name
        tool_name = None
        
        # Check if function is async
        is_async = inspect.iscoroutinefunction(func)
        
        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await _track_async_tool(func, tool_name, *args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                return _track_sync_tool(func, tool_name, *args, **kwargs)
            return sync_wrapper
    
    # Used as @track_tool() or @track_tool(name="...")
    def decorator(func: Callable) -> Callable:
        # Check if function is async
        is_async = inspect.iscoroutinefunction(func)
        
        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await _track_async_tool(func, name, *args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                return _track_sync_tool(func, name, *args, **kwargs)
            return sync_wrapper
    
    return decorator

