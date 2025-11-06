"""Tool instrumentation for GATI - Track custom @tool decorated functions.

This module provides automatic instrumentation for LangChain tools decorated with @tool.
It captures tool calls with inputs, outputs, timing, and errors.
"""

from __future__ import annotations

import time
import logging
import functools
from typing import Any, Callable, Optional, Dict
import inspect

logger = logging.getLogger("gati.tools")

# Try importing LangChain tool decorator
try:
    from langchain_core.tools import tool as langchain_tool, BaseTool  # type: ignore
    LANGCHAIN_TOOLS_AVAILABLE = True
except ImportError:
    try:
        from langchain.tools import tool as langchain_tool, BaseTool  # type: ignore
        LANGCHAIN_TOOLS_AVAILABLE = True
    except ImportError:
        LANGCHAIN_TOOLS_AVAILABLE = False
        langchain_tool = None  # type: ignore
        BaseTool = None  # type: ignore

from gati.observe import observe
from gati.core.event import ToolCallEvent
from gati.core.context import get_current_run_id, get_parent_event_id
from gati.utils.serializer import serialize

_instrumentation_applied = False
_original_tool_decorator = None
_original_base_tool_run = None


def _wrap_tool_function(func: Callable, tool_name: Optional[str] = None) -> Callable:
    """Wrap a tool function to track its execution.

    Args:
        func: The tool function to wrap
        tool_name: Optional name for the tool (defaults to function name)

    Returns:
        Wrapped function that tracks execution
    """
    if tool_name is None:
        tool_name = func.__name__

    # Check if function is async
    is_async = inspect.iscoroutinefunction(func)

    if is_async:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Async wrapper for tool tracking."""
            start_time = time.monotonic()
            error: Optional[Exception] = None
            output: Any = None

            try:
                # Execute the tool
                output = await func(*args, **kwargs)
                return output
            except Exception as e:
                error = e
                raise
            finally:
                # Track the tool call
                try:
                    duration_ms = (time.monotonic() - start_time) * 1000.0

                    # Get run_id from context
                    run_id = get_current_run_id() or ""

                    # Get parent event ID
                    parent_event_id = get_parent_event_id()

                    # Serialize inputs
                    tool_input = {}
                    if args:
                        tool_input["args"] = serialize(args)
                    if kwargs:
                        tool_input["kwargs"] = serialize(kwargs)

                    # Create tool call event
                    event_data: Dict[str, Any] = {
                        "tool_name": tool_name,
                        "input": tool_input,
                        "output": serialize(output) if output is not None else None,
                        "latency_ms": duration_ms,
                        "status": "error" if error else "completed"
                    }

                    if error:
                        event_data["error"] = {
                            "type": type(error).__name__,
                            "message": str(error),
                        }

                    event = ToolCallEvent(
                        run_id=run_id,
                        tool_name=tool_name,
                        input=tool_input,
                        output=serialize(output) if output is not None else None,
                        latency_ms=duration_ms,
                        data=event_data
                    )

                    # Set parent event if available
                    if parent_event_id:
                        event.parent_event_id = parent_event_id

                    observe.track_event(event)
                except Exception as tracking_error:
                    logger.debug(f"Failed to track tool call: {tracking_error}")

        return async_wrapper
    else:
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Sync wrapper for tool tracking."""
            start_time = time.monotonic()
            error: Optional[Exception] = None
            output: Any = None

            try:
                # Execute the tool
                output = func(*args, **kwargs)
                return output
            except Exception as e:
                error = e
                raise
            finally:
                # Track the tool call
                try:
                    duration_ms = (time.monotonic() - start_time) * 1000.0

                    # Get run_id from context
                    run_id = get_current_run_id() or ""

                    # Get parent event ID
                    parent_event_id = get_parent_event_id()

                    # Serialize inputs
                    tool_input = {}
                    if args:
                        tool_input["args"] = serialize(args)
                    if kwargs:
                        tool_input["kwargs"] = serialize(kwargs)

                    # Create tool call event
                    event_data: Dict[str, Any] = {
                        "tool_name": tool_name,
                        "input": tool_input,
                        "output": serialize(output) if output is not None else None,
                        "latency_ms": duration_ms,
                        "status": "error" if error else "completed"
                    }

                    if error:
                        event_data["error"] = {
                            "type": type(error).__name__,
                            "message": str(error),
                        }

                    event = ToolCallEvent(
                        run_id=run_id,
                        tool_name=tool_name,
                        input=tool_input,
                        output=serialize(output) if output is not None else None,
                        latency_ms=duration_ms,
                        data=event_data
                    )

                    # Set parent event if available
                    if parent_event_id:
                        event.parent_event_id = parent_event_id

                    observe.track_event(event)
                except Exception as tracking_error:
                    logger.debug(f"Failed to track tool call: {tracking_error}")

        return sync_wrapper


def _instrumented_tool_decorator(*args: Any, **kwargs: Any) -> Any:
    """Instrumented version of the @tool decorator that wraps tool functions."""

    def decorator(func: Callable) -> Any:
        # First, apply the original tool decorator
        tool_instance = _original_tool_decorator(func, *args[1:] if len(args) > 1 else [], **kwargs)

        # Get the tool name
        tool_name = getattr(tool_instance, 'name', func.__name__)

        # Wrap the actual function that gets called
        if hasattr(tool_instance, 'func'):
            # The tool has a func attribute, wrap it
            original_func = tool_instance.func
            tool_instance.func = _wrap_tool_function(original_func, tool_name)
        elif hasattr(tool_instance, '_run'):
            # Wrap the _run method for BaseTool subclasses
            original_run = tool_instance._run
            tool_instance._run = _wrap_tool_function(original_run, tool_name)

        # Also wrap invoke method if it exists
        if hasattr(tool_instance, 'invoke'):
            original_invoke = tool_instance.invoke

            @functools.wraps(original_invoke)
            def wrapped_invoke(input: Any, *invoke_args: Any, **invoke_kwargs: Any) -> Any:
                start_time = time.monotonic()
                error: Optional[Exception] = None
                output: Any = None

                try:
                    output = original_invoke(input, *invoke_args, **invoke_kwargs)
                    return output
                except Exception as e:
                    error = e
                    raise
                finally:
                    try:
                        duration_ms = (time.monotonic() - start_time) * 1000.0
                        run_id = get_current_run_id() or ""
                        parent_event_id = get_parent_event_id()

                        event = ToolCallEvent(
                            run_id=run_id,
                            tool_name=tool_name,
                            input=serialize(input),
                            output=serialize(output) if output is not None else None,
                            latency_ms=duration_ms,
                            data={
                                "tool_name": tool_name,
                                "input": serialize(input),
                                "output": serialize(output) if output is not None else None,
                                "latency_ms": duration_ms,
                                "status": "error" if error else "completed",
                                "error": {"type": type(error).__name__, "message": str(error)} if error else None
                            }
                        )

                        if parent_event_id:
                            event.parent_event_id = parent_event_id

                        observe.track_event(event)
                    except Exception as tracking_error:
                        logger.debug(f"Failed to track tool invoke: {tracking_error}")

            tool_instance.invoke = wrapped_invoke

        return tool_instance

    # Handle both @tool and @tool() usage
    if len(args) == 1 and callable(args[0]) and not kwargs:
        # Called as @tool without parentheses
        return decorator(args[0])
    else:
        # Called as @tool() or @tool(name="...")
        return decorator


def _wrap_base_tool_invoke(original_invoke):
    """Wrap BaseTool.invoke to track all tool calls."""

    @functools.wraps(original_invoke)
    def wrapped_invoke(self, input: Any, config: Optional[Any] = None, **kwargs: Any) -> Any:
        """Wrapped invoke that tracks tool execution."""
        start_time = time.monotonic()
        error: Optional[Exception] = None
        output: Any = None
        tool_name = getattr(self, 'name', self.__class__.__name__)

        try:
            output = original_invoke(self, input, config, **kwargs)
            return output
        except Exception as e:
            error = e
            raise
        finally:
            try:
                duration_ms = (time.monotonic() - start_time) * 1000.0
                run_id = get_current_run_id() or ""
                parent_event_id = get_parent_event_id()

                event = ToolCallEvent(
                    run_id=run_id,
                    tool_name=tool_name,
                    input=serialize(input),
                    output=serialize(output) if output is not None else None,
                    latency_ms=duration_ms,
                    data={
                        "tool_name": tool_name,
                        "input": serialize(input),
                        "output": serialize(output) if output is not None else None,
                        "latency_ms": duration_ms,
                        "status": "error" if error else "completed",
                        "error": {"type": type(error).__name__, "message": str(error)} if error else None
                    }
                )

                if parent_event_id:
                    event.parent_event_id = parent_event_id

                observe.track_event(event)
            except Exception as tracking_error:
                logger.debug(f"Failed to track tool invoke: {tracking_error}")

    return wrapped_invoke


def instrument_tools() -> bool:
    """Instrument LangChain BaseTool.invoke to automatically track all tool calls.

    Returns:
        True if instrumentation succeeded, False otherwise
    """
    global _instrumentation_applied, _original_tool_decorator, _original_base_tool_run

    if not LANGCHAIN_TOOLS_AVAILABLE:
        logger.info("LangChain tools not available")
        return False

    if _instrumentation_applied:
        logger.debug("Tool instrumentation already applied")
        return True

    try:
        # Instrument BaseTool.invoke() method - this catches ALL tool invocations
        if BaseTool is not None:
            original_invoke = BaseTool.invoke
            _original_base_tool_run = original_invoke
            BaseTool.invoke = _wrap_base_tool_invoke(original_invoke)
            logger.info("BaseTool.invoke instrumented for tracking")

        # Also store original tool decorator for future use
        _original_tool_decorator = langchain_tool

        # Replace the tool decorator in langchain_core.tools
        import langchain_core.tools
        langchain_core.tools.tool = _instrumented_tool_decorator

        # Also replace in langchain.tools if it exists
        try:
            import langchain.tools
            langchain.tools.tool = _instrumented_tool_decorator
        except (ImportError, AttributeError):
            pass

        _instrumentation_applied = True
        logger.info("Tool instrumentation enabled")
        return True

    except Exception as e:
        logger.error(f"Failed to instrument tools: {e}")
        return False


__all__ = ["instrument_tools"]
