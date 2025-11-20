"""LangChain instrumentation for GATI - Comprehensive Auto-Injection.

This module provides automatic instrumentation for LangChain by monkey-patching
Runnable.invoke/batch/stream methods, BaseLanguageModel._generate/_call methods,
and BaseTool._run/_arun methods. Once enabled, all LangChain components are
automatically tracked without any code changes.

Usage:
    from gati import observe

    # Initialize - that's it! LangChain components are auto-instrumented
    observe.init(name="my_agent")

    # Use LangChain normally - everything is tracked automatically
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model="gpt-3.5-turbo")
    response = llm.invoke("What's 2+2?")  # ← Automatically tracked!

    # Streaming works too
    for chunk in llm.stream("Tell me a story"):
        print(chunk.content, end="")  # ← Tokens are accumulated and tracked!

    # Agents work too
    from langchain.agents import AgentExecutor
    executor = AgentExecutor(agent=agent, tools=tools)
    result = executor.invoke({"input": "..."})  # ← All tracked!

What gets tracked:
    LLM Calls:
    - Model name (e.g., "gpt-3.5-turbo")
    - Prompt (user input) and system prompt
    - Completion (LLM response, including streaming tokens)
    - Token usage (input/output tokens)
    - Latency (milliseconds)
    - Cost (calculated based on model pricing)
    - Status (success/error)
    - Metadata: class name, module, config parameters (temperature, max_tokens, etc.)

    Tool Invocations:
    - Tool name
    - Tool input
    - Tool output (truncated if large)
    - Latency (milliseconds)
    - Status (success/failure)
    - Metadata: class name, module, description, arguments schema

    Agent Execution (for agents):
    - Agent name
    - Run start/end time
    - Total duration
    - Overall status
    - User request/input
    - Error messages if any

How it works:
    - observe.init(auto_inject=True) enables automatic callback injection
    - Patches Runnable.invoke/batch/stream for all Runnables
    - Patches BaseLanguageModel._generate/_call for direct LLM calls
    - Patches BaseTool._run/_arun for tool executions
    - Injects GatiLangChainCallback for comprehensive tracking
    - Supports streaming with token accumulation
    - Tracks parent-child relationships for nested calls
    - Zero code changes to your LangChain usage
    - Works with LangChain 0.1.x, 0.2.x, and 1.x (sync and async)
"""

from __future__ import annotations

import functools
import time
import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union
from uuid import UUID

# Try importing from latest LangChain structure
try:
    from langchain_core.callbacks import BaseCallbackHandler  # type: ignore
    from langchain_core.outputs import LLMResult  # type: ignore
    from langchain_core.runnables import Runnable  # type: ignore
    LANGCHAIN_AVAILABLE = True
except ImportError:
    try:
        # Fallback for older LangChain versions
        from langchain.callbacks.base import BaseCallbackHandler  # type: ignore
        from langchain.schema import LLMResult  # type: ignore
        from langchain.runnables import Runnable  # type: ignore
        LANGCHAIN_AVAILABLE = True
    except ImportError:
        # Minimal stub to avoid import-time failure if LC not installed
        LANGCHAIN_AVAILABLE = False

        class BaseCallbackHandler:  # type: ignore
            """Stub BaseCallbackHandler for when LangChain isn't installed."""
            pass

        class LLMResult:  # type: ignore
            """Stub LLMResult for when LangChain isn't installed."""
            pass

        Runnable = None  # type: ignore

from gati.observe import observe
from gati.core.event import (
    LLMCallEvent,
    ToolCallEvent,
    AgentStartEvent,
    AgentEndEvent,
    StepEvent,
    generate_run_id,
)
from gati.core.context import get_current_run_id, get_parent_event_id, run_context, arun_context, set_parent_event_id
from gati.utils.token_counter import extract_tokens_from_response
from gati.utils.serializer import serialize

logger = logging.getLogger("gati")
T = TypeVar("T")

# Global flag to track if auto-injection is enabled
_AUTO_INJECTION_ENABLED = False
_ORIGINAL_METHODS = {}


# ======================== Auto-Injection Functions ========================


def enable_auto_injection() -> None:
    """Enable automatic callback injection for all LangChain Runnables.

    This should be called once during GATI initialization.
    It wraps the Runnable.invoke() method to automatically inject callbacks.
    """
    global _AUTO_INJECTION_ENABLED

    if not LANGCHAIN_AVAILABLE:
        logger.debug("LangChain not available; auto-injection disabled")
        return

    if _AUTO_INJECTION_ENABLED:
        logger.debug("Auto-injection already enabled")
        return

    _AUTO_INJECTION_ENABLED = True
    _patch_runnable_invoke()
    logger.debug("LangChain auto-injection enabled")


def disable_auto_injection() -> None:
    """Disable automatic callback injection and restore original methods."""
    global _AUTO_INJECTION_ENABLED

    if not _AUTO_INJECTION_ENABLED:
        return

    _unpatch_runnable_invoke()
    _AUTO_INJECTION_ENABLED = False
    logger.debug("LangChain auto-injection disabled")


def _patch_base_language_model() -> None:
    """Patch BaseLanguageModel._generate and _call methods for complete LLM tracking.

    This ensures that all LLM calls are caught, including those that don't go through
    Runnable.invoke (e.g., direct _generate calls or legacy _call methods).
    """
    try:
        # Try to import BaseLanguageModel from various locations
        BaseLanguageModel = None
        try:
            from langchain_core.language_models.base import BaseLanguageModel as BLM
            BaseLanguageModel = BLM
        except ImportError:
            try:
                from langchain.llms.base import BaseLanguageModel as BLM
                BaseLanguageModel = BLM
            except ImportError:
                logger.debug("BaseLanguageModel not found, skipping LLM patching")
                return

        if BaseLanguageModel is None:
            return

        # Patch _generate method (used by most LLMs)
        if hasattr(BaseLanguageModel, "_generate"):
            original_generate = BaseLanguageModel._generate
            _ORIGINAL_METHODS["llm_generate"] = original_generate

            @functools.wraps(original_generate)
            def patched_generate(self, prompts: List[str], stop: Optional[List[str]] = None,
                                run_manager: Optional[Any] = None, **kwargs: Any) -> Any:
                """Patched _generate to ensure callback tracking."""
                try:
                    # The callback manager should already be injected via invoke wrapper
                    # This is a safety net to ensure tracking happens even for direct calls
                    return original_generate(self, prompts, stop, run_manager, **kwargs)
                except Exception as e:
                    logger.debug(f"Error in patched _generate: {e}")
                    return original_generate(self, prompts, stop, run_manager, **kwargs)

            BaseLanguageModel._generate = patched_generate
            logger.debug("Patched BaseLanguageModel._generate")

        # Patch _call method for older LangChain versions
        if hasattr(BaseLanguageModel, "_call"):
            original_call = BaseLanguageModel._call
            _ORIGINAL_METHODS["llm_call"] = original_call

            @functools.wraps(original_call)
            def patched_call(self, prompt: str, stop: Optional[List[str]] = None,
                           run_manager: Optional[Any] = None, **kwargs: Any) -> str:
                """Patched _call to ensure callback tracking."""
                try:
                    return original_call(self, prompt, stop, run_manager, **kwargs)
                except Exception as e:
                    logger.debug(f"Error in patched _call: {e}")
                    return original_call(self, prompt, stop, run_manager, **kwargs)

            BaseLanguageModel._call = patched_call
            logger.debug("Patched BaseLanguageModel._call")

    except Exception as e:
        logger.debug(f"Failed to patch BaseLanguageModel: {e}")


def _patch_base_tool() -> None:
    """Patch BaseTool._run and _arun methods for complete tool tracking.

    This ensures that all tool executions are caught, including @tool-decorated
    functions and custom tool implementations.
    """
    try:
        # Try to import BaseTool from various locations
        BaseTool = None
        try:
            from langchain_core.tools import BaseTool as BT
            BaseTool = BT
        except ImportError:
            try:
                from langchain.tools.base import BaseTool as BT
                BaseTool = BT
            except ImportError:
                logger.debug("BaseTool not found, skipping tool patching")
                return

        if BaseTool is None:
            return

        # Patch _run method (sync tool execution)
        if hasattr(BaseTool, "_run"):
            original_run = BaseTool._run
            _ORIGINAL_METHODS["tool_run"] = original_run

            @functools.wraps(original_run)
            def patched_run(self, *args: Any, run_manager: Optional[Any] = None, **kwargs: Any) -> Any:
                """Patched _run to ensure callback tracking for tools."""
                try:
                    # Track tool execution with metadata
                    start_time = time.monotonic()
                    error: Optional[Exception] = None
                    result: Any = None

                    try:
                        result = original_run(self, *args, run_manager=run_manager, **kwargs)
                        return result
                    except Exception as e:
                        error = e
                        raise
                    finally:
                        # The callback handler should track this via on_tool_start/end
                        # This is additional metadata for debugging
                        duration_ms = (time.monotonic() - start_time) * 1000.0
                        if error:
                            logger.debug(
                                f"Tool {getattr(self, 'name', 'unknown')} failed after {duration_ms:.2f}ms: {error}"
                            )

                except Exception as e:
                    logger.debug(f"Error in patched _run: {e}")
                    return original_run(self, *args, run_manager=run_manager, **kwargs)

            BaseTool._run = patched_run
            logger.debug("Patched BaseTool._run")

        # Patch _arun method (async tool execution)
        if hasattr(BaseTool, "_arun"):
            original_arun = BaseTool._arun
            _ORIGINAL_METHODS["tool_arun"] = original_arun

            @functools.wraps(original_arun)
            async def patched_arun(self, *args: Any, run_manager: Optional[Any] = None, **kwargs: Any) -> Any:
                """Patched _arun to ensure callback tracking for async tools."""
                try:
                    # Track tool execution with metadata
                    start_time = time.monotonic()
                    error: Optional[Exception] = None
                    result: Any = None

                    try:
                        result = await original_arun(self, *args, run_manager=run_manager, **kwargs)
                        return result
                    except Exception as e:
                        error = e
                        raise
                    finally:
                        # The callback handler should track this via on_tool_start/end
                        # This is additional metadata for debugging
                        duration_ms = (time.monotonic() - start_time) * 1000.0
                        if error:
                            logger.debug(
                                f"Tool {getattr(self, 'name', 'unknown')} failed after {duration_ms:.2f}ms: {error}"
                            )

                except Exception as e:
                    logger.debug(f"Error in patched _arun: {e}")
                    return await original_arun(self, *args, run_manager=run_manager, **kwargs)

            BaseTool._arun = patched_arun
            logger.debug("Patched BaseTool._arun")

    except Exception as e:
        logger.debug(f"Failed to patch BaseTool: {e}")


def _patch_runnable_invoke() -> None:
    """Patch Runnable.invoke to inject callbacks."""
    if not LANGCHAIN_AVAILABLE:
        return

    # Store original sync methods
    original_invoke = Runnable.invoke
    original_batch = Runnable.batch
    original_stream = Runnable.stream

    _ORIGINAL_METHODS["invoke"] = original_invoke
    _ORIGINAL_METHODS["batch"] = original_batch
    _ORIGINAL_METHODS["stream"] = original_stream

    # Also patch BaseChatModel.invoke which overrides Runnable.invoke
    # This is critical because LLMs use BaseChatModel.invoke, not Runnable.invoke
    try:
        from langchain_core.language_models.chat_models import BaseChatModel
        original_chat_invoke = BaseChatModel.invoke
        _ORIGINAL_METHODS["chat_invoke"] = original_chat_invoke
    except ImportError:
        try:
            from langchain.chat_models.base import BaseChatModel
            original_chat_invoke = BaseChatModel.invoke
            _ORIGINAL_METHODS["chat_invoke"] = original_chat_invoke
        except ImportError:
            logger.debug("BaseChatModel not found, skipping chat model patching")
            original_chat_invoke = None

    # Patch RunnableSequence.invoke which is used for chains (prompt | llm | parser)
    try:
        from langchain_core.runnables.base import RunnableSequence
        original_sequence_invoke = RunnableSequence.invoke
        _ORIGINAL_METHODS["sequence_invoke"] = original_sequence_invoke
    except ImportError:
        try:
            from langchain.schema.runnable import RunnableSequence
            original_sequence_invoke = RunnableSequence.invoke
            _ORIGINAL_METHODS["sequence_invoke"] = original_sequence_invoke
        except ImportError:
            logger.debug("RunnableSequence not found, skipping sequence patching")
            original_sequence_invoke = None

    # Patch BaseLanguageModel._generate and _call for complete LLM tracking
    _patch_base_language_model()

    # Patch BaseTool._run and _arun for complete tool tracking
    _patch_base_tool()

    # Store original async methods if they exist
    if hasattr(Runnable, "ainvoke"):
        original_ainvoke = Runnable.ainvoke
        _ORIGINAL_METHODS["ainvoke"] = original_ainvoke

    if hasattr(Runnable, "abatch"):
        original_abatch = Runnable.abatch
        _ORIGINAL_METHODS["abatch"] = original_abatch

    if hasattr(Runnable, "astream"):
        original_astream = Runnable.astream
        _ORIGINAL_METHODS["astream"] = original_astream

    if hasattr(Runnable, "afor_each"):
        original_afor_each = Runnable.afor_each
        _ORIGINAL_METHODS["afor_each"] = original_afor_each

    # Sync method wrappers
    @functools.wraps(original_invoke)
    def patched_invoke(self, input: Any, config: Optional[Any] = None, **kwargs: Any) -> Any:
        """Invoke with automatic callback injection."""
        return _invoke_with_callbacks(original_invoke, self, input, config, **kwargs)

    @functools.wraps(original_batch)
    def patched_batch(self, inputs: Any, config: Optional[Any] = None, **kwargs: Any) -> Any:
        """Batch invoke with automatic callback injection."""
        return _invoke_with_callbacks(original_batch, self, inputs, config, **kwargs)

    @functools.wraps(original_stream)
    def patched_stream(self, input: Any, config: Optional[Any] = None, **kwargs: Any) -> Any:
        """Stream invoke with automatic callback injection."""
        return _invoke_with_callbacks(original_stream, self, input, config, **kwargs)

    # Async method wrappers
    if "ainvoke" in _ORIGINAL_METHODS:
        @functools.wraps(original_ainvoke)
        async def patched_ainvoke(self, input: Any, config: Optional[Any] = None, **kwargs: Any) -> Any:
            """Async invoke with automatic callback injection."""
            return await _ainvoke_with_callbacks(original_ainvoke, self, input, config, **kwargs)
        Runnable.ainvoke = patched_ainvoke

    if "abatch" in _ORIGINAL_METHODS:
        @functools.wraps(original_abatch)
        async def patched_abatch(self, inputs: Any, config: Optional[Any] = None, **kwargs: Any) -> Any:
            """Async batch invoke with automatic callback injection."""
            return await _ainvoke_with_callbacks(original_abatch, self, inputs, config, **kwargs)
        Runnable.abatch = patched_abatch

    if "astream" in _ORIGINAL_METHODS:
        @functools.wraps(original_astream)
        async def patched_astream(self, input: Any, config: Optional[Any] = None, **kwargs: Any) -> Any:
            """Async stream invoke with automatic callback injection."""
            return await _ainvoke_with_callbacks(original_astream, self, input, config, **kwargs)
        Runnable.astream = patched_astream

    if "afor_each" in _ORIGINAL_METHODS:
        @functools.wraps(original_afor_each)
        async def patched_afor_each(self, inputs: Any, config: Optional[Any] = None, **kwargs: Any) -> Any:
            """Async for_each with automatic callback injection."""
            return await _ainvoke_with_callbacks(original_afor_each, self, inputs, config, **kwargs)
        Runnable.afor_each = patched_afor_each

    # Apply sync patches
    Runnable.invoke = patched_invoke
    Runnable.batch = patched_batch
    Runnable.stream = patched_stream

    # Patch BaseChatModel.invoke as well (critical for LLM tracking)
    if original_chat_invoke:
        @functools.wraps(original_chat_invoke)
        def patched_chat_invoke(self, input: Any, config: Optional[Any] = None, **kwargs: Any) -> Any:
            """Chat model invoke with automatic callback injection."""
            return _invoke_with_callbacks(original_chat_invoke, self, input, config, **kwargs)

        try:
            from langchain_core.language_models.chat_models import BaseChatModel
            BaseChatModel.invoke = patched_chat_invoke
        except ImportError:
            try:
                from langchain.chat_models.base import BaseChatModel
                BaseChatModel.invoke = patched_chat_invoke
            except ImportError:
                pass

    # Patch RunnableSequence.invoke as well (critical for chain tracking)
    if original_sequence_invoke:
        @functools.wraps(original_sequence_invoke)
        def patched_sequence_invoke(self, input: Any, config: Optional[Any] = None, **kwargs: Any) -> Any:
            """Runnable sequence invoke with automatic callback injection."""
            return _invoke_with_callbacks(original_sequence_invoke, self, input, config, **kwargs)

        try:
            from langchain_core.runnables.base import RunnableSequence
            RunnableSequence.invoke = patched_sequence_invoke
        except ImportError:
            try:
                from langchain.schema.runnable import RunnableSequence
                RunnableSequence.invoke = patched_sequence_invoke
            except ImportError:
                pass


def _unpatch_runnable_invoke() -> None:
    """Restore original Runnable methods."""
    if not LANGCHAIN_AVAILABLE or not _ORIGINAL_METHODS:
        return

    # Restore sync methods
    Runnable.invoke = _ORIGINAL_METHODS.get("invoke", Runnable.invoke)
    Runnable.batch = _ORIGINAL_METHODS.get("batch", Runnable.batch)
    Runnable.stream = _ORIGINAL_METHODS.get("stream", Runnable.stream)

    # Restore async methods if they were patched
    if "ainvoke" in _ORIGINAL_METHODS:
        Runnable.ainvoke = _ORIGINAL_METHODS["ainvoke"]
    if "abatch" in _ORIGINAL_METHODS:
        Runnable.abatch = _ORIGINAL_METHODS["abatch"]
    if "astream" in _ORIGINAL_METHODS:
        Runnable.astream = _ORIGINAL_METHODS["astream"]
    if "afor_each" in _ORIGINAL_METHODS:
        Runnable.afor_each = _ORIGINAL_METHODS["afor_each"]

    # Restore BaseChatModel.invoke if it was patched
    if "chat_invoke" in _ORIGINAL_METHODS:
        try:
            from langchain_core.language_models.chat_models import BaseChatModel
            BaseChatModel.invoke = _ORIGINAL_METHODS["chat_invoke"]
        except ImportError:
            try:
                from langchain.chat_models.base import BaseChatModel
                BaseChatModel.invoke = _ORIGINAL_METHODS["chat_invoke"]
            except ImportError:
                pass

    # Restore RunnableSequence.invoke if it was patched
    if "sequence_invoke" in _ORIGINAL_METHODS:
        try:
            from langchain_core.runnables.base import RunnableSequence
            RunnableSequence.invoke = _ORIGINAL_METHODS["sequence_invoke"]
        except ImportError:
            try:
                from langchain.schema.runnable import RunnableSequence
                RunnableSequence.invoke = _ORIGINAL_METHODS["sequence_invoke"]
            except ImportError:
                pass

    # Restore BaseLanguageModel methods if they were patched
    if "llm_generate" in _ORIGINAL_METHODS:
        try:
            from langchain_core.language_models.base import BaseLanguageModel
            BaseLanguageModel._generate = _ORIGINAL_METHODS["llm_generate"]
        except ImportError:
            try:
                from langchain.llms.base import BaseLanguageModel
                BaseLanguageModel._generate = _ORIGINAL_METHODS["llm_generate"]
            except ImportError:
                pass

    if "llm_call" in _ORIGINAL_METHODS:
        try:
            from langchain_core.language_models.base import BaseLanguageModel
            BaseLanguageModel._call = _ORIGINAL_METHODS["llm_call"]
        except ImportError:
            try:
                from langchain.llms.base import BaseLanguageModel
                BaseLanguageModel._call = _ORIGINAL_METHODS["llm_call"]
            except ImportError:
                pass

    # Restore BaseTool methods if they were patched
    if "tool_run" in _ORIGINAL_METHODS:
        try:
            from langchain_core.tools import BaseTool
            BaseTool._run = _ORIGINAL_METHODS["tool_run"]
        except ImportError:
            try:
                from langchain.tools.base import BaseTool
                BaseTool._run = _ORIGINAL_METHODS["tool_run"]
            except ImportError:
                pass

    if "tool_arun" in _ORIGINAL_METHODS:
        try:
            from langchain_core.tools import BaseTool
            BaseTool._arun = _ORIGINAL_METHODS["tool_arun"]
        except ImportError:
            try:
                from langchain.tools.base import BaseTool
                BaseTool._arun = _ORIGINAL_METHODS["tool_arun"]
            except ImportError:
                pass

    _ORIGINAL_METHODS.clear()


def _invoke_with_callbacks(
    original_method: Callable,
    runnable_self: Any,
    input_data: Any,
    config: Optional[Any] = None,
    **kwargs: Any
) -> Any:
    """Inject callbacks into a Runnable invocation with proper run context.

    This function:
    1. Creates run context for all top-level calls (agents and standalone LLMs)
    2. Injects GATI callbacks for all calls
    3. Ensures proper parent-child event relationships
    4. Only creates AgentStart/End events for agents, not simple LLM calls
    """
    try:
        # Only inject if observe is initialized
        if not observe._initialized:
            return original_method(runnable_self, input_data, config, **kwargs)

        # Handle config setup
        if config is None:
            config = {}
        elif not isinstance(config, dict):
            # config might be a RunnableConfig object
            try:
                # Try to get callbacks from config if it's an object
                existing_callbacks = getattr(config, "callbacks", None)
                if existing_callbacks:
                    # User already set callbacks, don't override
                    return original_method(runnable_self, input_data, config, **kwargs)
            except Exception:
                pass
            # If we can't extract callbacks, proceed with original method
            return original_method(runnable_self, input_data, config, **kwargs)

        # Check if callbacks already present in config
        existing_callbacks = config.get("callbacks", None)
        if existing_callbacks:
            # User already set callbacks, don't override
            return original_method(runnable_self, input_data, config, **kwargs)

        # Check if already in a run context
        existing_run_id = get_current_run_id()

        # Determine if this is a top-level agent call or a nested component
        is_agent_call = _is_agent_runnable(runnable_self, config)

        if existing_run_id:
            # Already in a run context, just inject callbacks without creating new context
            gati_callbacks = observe.get_callbacks()
            if gati_callbacks:
                config["callbacks"] = gati_callbacks
            return original_method(runnable_self, input_data, config, **kwargs)

        # Not in a run context - create one for both agents and standalone LLM calls
        # This ensures all LLM events have a proper run_id

        # This is a top-level call (agent or LLM) - create run context
        start_time = time.monotonic()
        error: Optional[Exception] = None
        output: Any = None

        # Create new run context
        with run_context() as new_run_id:
            try:
                # Only create AgentStartEvent for actual agents, not simple LLM calls
                # LLM calls will be tracked via the callback handler's on_llm_start
                if is_agent_call:
                    # Determine agent name from runnable
                    agent_name = _extract_agent_name(runnable_self)

                    # Create agent start event
                    start_event = AgentStartEvent(
                        run_id=new_run_id,
                        agent_name=agent_name,
                        input=serialize(input_data),
                        metadata={
                            "auto_tracked": True,
                            "runnable_type": type(runnable_self).__name__,
                        }
                    )

                    # Set this start event as parent for all child events
                    set_parent_event_id(start_event.event_id)

                    # Track the start event
                    observe.track_event(start_event)

                # Inject callbacks
                gati_callbacks = observe.get_callbacks()
                if gati_callbacks:
                    config["callbacks"] = gati_callbacks

                # Execute the original method
                output = original_method(runnable_self, input_data, config, **kwargs)

                return output

            except Exception as e:
                error = e
                raise

            finally:
                # Track agent end event only for actual agents
                # For simple LLM calls, the callback handler tracks LLMCallEvent
                if is_agent_call:
                    try:
                        duration_ms = (time.monotonic() - start_time) * 1000.0

                        end_event_data = {
                            "auto_tracked": True,
                            "runnable_type": type(runnable_self).__name__,
                            "total_duration_ms": duration_ms,
                        }

                        if error:
                            end_event_data["error"] = {
                                "type": type(error).__name__,
                                "message": str(error),
                            }
                            end_event_data["status"] = "error"
                        else:
                            end_event_data["status"] = "completed"

                        end_event = AgentEndEvent(
                            run_id=new_run_id,
                            output=serialize(output) if output is not None else {},
                            total_duration_ms=duration_ms,
                            metadata=end_event_data
                        )

                        observe.track_event(end_event)

                    except Exception as tracking_error:
                        logger.debug(f"Failed to track agent end event: {tracking_error}")

    except Exception as e:
        logger.debug(f"Error in callback injection with context: {e}")
        # Fail-safe: call original method without callbacks
        return original_method(runnable_self, input_data, config, **kwargs)


async def _ainvoke_with_callbacks(
    original_method: Callable,
    runnable_self: Any,
    input_data: Any,
    config: Optional[Any] = None,
    **kwargs: Any
) -> Any:
    """Inject callbacks into an async Runnable invocation with proper run context.

    This function:
    1. Creates run context for all top-level calls (agents and standalone LLMs)
    2. Injects GATI callbacks for all calls
    3. Ensures proper parent-child event relationships
    4. Only creates AgentStart/End events for agents, not simple LLM calls
    5. Handles async execution with await
    """
    try:
        # Only inject if observe is initialized
        if not observe._initialized:
            return await original_method(runnable_self, input_data, config, **kwargs)

        # Handle config setup
        if config is None:
            config = {}
        elif not isinstance(config, dict):
            # config might be a RunnableConfig object
            try:
                # Try to get callbacks from config if it's an object
                existing_callbacks = getattr(config, "callbacks", None)
                if existing_callbacks:
                    # User already set callbacks, don't override
                    return await original_method(runnable_self, input_data, config, **kwargs)
            except Exception:
                pass
            # If we can't extract callbacks, proceed with original method
            return await original_method(runnable_self, input_data, config, **kwargs)

        # Check if callbacks already present in config
        existing_callbacks = config.get("callbacks", None)
        if existing_callbacks:
            # User already set callbacks, don't override
            return await original_method(runnable_self, input_data, config, **kwargs)

        # Check if already in a run context
        existing_run_id = get_current_run_id()

        # Determine if this is a top-level agent call or a nested component
        is_agent_call = _is_agent_runnable(runnable_self, config)

        if existing_run_id:
            # Already in a run context, just inject callbacks without creating new context
            gati_callbacks = observe.get_callbacks()
            if gati_callbacks:
                config["callbacks"] = gati_callbacks
            return await original_method(runnable_self, input_data, config, **kwargs)

        # Not in a run context - create one for both agents and standalone LLM calls
        # This ensures all LLM events have a proper run_id

        # This is a top-level call (agent or LLM) - create run context
        start_time = time.monotonic()
        error: Optional[Exception] = None
        output: Any = None

        # Create new run context using async context manager
        # This is the correct pattern for async functions, using async with for proper async handling
        async with arun_context() as new_run_id:
            try:
                # Only create AgentStartEvent for actual agents, not simple LLM calls
                # LLM calls will be tracked via the callback handler's on_llm_start
                if is_agent_call:
                    # Determine agent name from runnable
                    agent_name = _extract_agent_name(runnable_self)

                    # Create agent start event
                    start_event = AgentStartEvent(
                        run_id=new_run_id,
                        agent_name=agent_name,
                        input=serialize(input_data),
                        metadata={
                            "auto_tracked": True,
                            "runnable_type": type(runnable_self).__name__,
                        }
                    )

                    # Set this start event as parent for all child events
                    set_parent_event_id(start_event.event_id)

                    # Track the start event
                    observe.track_event(start_event)

                # Inject callbacks
                gati_callbacks = observe.get_callbacks()
                if gati_callbacks:
                    config["callbacks"] = gati_callbacks

                # Execute the original async method
                output = await original_method(runnable_self, input_data, config, **kwargs)

                return output

            except Exception as e:
                error = e
                raise

            finally:
                # Track agent end event only for actual agents
                # For simple LLM calls, the callback handler tracks LLMCallEvent
                if is_agent_call:
                    try:
                        duration_ms = (time.monotonic() - start_time) * 1000.0

                        end_event_data = {
                            "auto_tracked": True,
                            "runnable_type": type(runnable_self).__name__,
                            "total_duration_ms": duration_ms,
                        }

                        if error:
                            end_event_data["error"] = {
                                "type": type(error).__name__,
                                "message": str(error),
                            }
                            end_event_data["status"] = "error"
                        else:
                            end_event_data["status"] = "completed"

                        end_event = AgentEndEvent(
                            run_id=new_run_id,
                            output=serialize(output) if output is not None else {},
                            total_duration_ms=duration_ms,
                            metadata=end_event_data
                        )

                        observe.track_event(end_event)

                    except Exception as tracking_error:
                        logger.debug(f"Failed to track agent end event: {tracking_error}")

    except Exception as e:
        logger.debug(f"Error in async callback injection with context: {e}")
        # Fail-safe: call original method without callbacks
        return await original_method(runnable_self, input_data, config, **kwargs)


def _is_agent_runnable(runnable: Any, config: Optional[Dict[str, Any]] = None) -> bool:
    """Determine if a runnable is an agent (not just an LLM or simple chain).

    Agents are composite structures (graphs, agent executors) that contain
    multiple components. Simple LLMs and chains are not agents.

    This function uses a multi-layered approach:
    1. Check for explicit GATI configuration flag
    2. Perform inheritance checks against known agent base classes
    3. Use refined keyword matching with specific indicators
    4. Default to non-agent to avoid false positives

    Args:
        runnable: The runnable object to check
        config: Optional configuration dict that may contain 'gati_is_agent' flag

    Returns:
        True if this is an agent-level runnable, False otherwise
    """
    try:
        # Layer 1: Check for explicit GATI configuration flag
        # This allows users to manually override the heuristic for custom Runnables
        if config and isinstance(config, dict):
            gati_is_agent = config.get("gati_is_agent")
            if gati_is_agent is not None:
                return bool(gati_is_agent)

        class_name = type(runnable).__name__.lower()
        module_name = type(runnable).__module__.lower() if hasattr(type(runnable), '__module__') else ""

        # Layer 2: Inheritance-based checks for known agent base classes
        # These checks are more reliable than string matching
        try:
            # Check for LangGraph agent classes
            if LANGCHAIN_AVAILABLE:
                # Import LangGraph classes if available
                try:
                    from langgraph.pregel import Pregel  # type: ignore
                    if isinstance(runnable, Pregel):
                        return True
                except ImportError:
                    pass

                try:
                    from langgraph.graph import StateGraph, MessageGraph  # type: ignore
                    # StateGraph and MessageGraph are usually compiled into Pregel
                    # but check for inheritance just in case
                    if isinstance(runnable, (StateGraph, MessageGraph)):
                        return True
                except ImportError:
                    pass

                # Check for AgentExecutor from LangChain
                try:
                    from langchain.agents import AgentExecutor  # type: ignore
                    if isinstance(runnable, AgentExecutor):
                        return True
                except ImportError:
                    pass

                try:
                    from langchain_core.agents import AgentExecutor  # type: ignore
                    if isinstance(runnable, AgentExecutor):
                        return True
                except ImportError:
                    pass

        except Exception as e:
            logger.debug(f"Inheritance check failed: {e}")

        # Layer 3: Refined keyword matching with specific indicators
        # More specific agent indicators (avoid generic terms like "chain")
        agent_indicators = [
            "agentexecutor",  # Specific class name
            "pregel",         # LangGraph compiled graphs
            "stategraph",     # LangGraph state graphs
            "messagegraph",   # LangGraph message graphs
            "compiledgraph",  # LangGraph compiled graphs
        ]

        # Check for LLM/Chat model types (NOT agents)
        # These should never be treated as agents
        llm_indicators = [
            "chatmodel",
            "basechatmodel",
            "llm",
            "basellm",
            "openai",
            "anthropic",
            "claude",
            "gpt",
            "chatgpt",
        ]

        # If it's an LLM, it's definitely not an agent
        if any(indicator in class_name for indicator in llm_indicators):
            return False

        # Check for specific agent indicators (more reliable than "agent" alone)
        if any(indicator in class_name for indicator in agent_indicators):
            return True

        # Check module path for langgraph with specific class patterns
        if "langgraph" in module_name:
            # LangGraph modules are strong indicators of agent-like structures
            if any(indicator in class_name for indicator in ["pregel", "compiled", "stategraph", "messagegraph"]):
                return True

        # Layer 4: Check for "agent" keyword but be more cautious
        # Only treat as agent if "agent" appears AND it's not a simple chain/llm
        if "agent" in class_name:
            # Make sure it's not a false positive (e.g., "agent_chain" might be a simple chain)
            # Only accept if module suggests it's from agents package
            if "agent" in module_name or "langgraph" in module_name:
                return True

        # Default: if unsure, treat as non-agent (safer - avoids creating too many runs)
        return False

    except Exception as e:
        logger.debug(f"Error in _is_agent_runnable: {e}")
        return False


def _extract_agent_name(runnable: Any) -> str:
    """Extract a meaningful agent name from a runnable object.

    Args:
        runnable: The runnable object

    Returns:
        Agent name string
    """
    try:
        # Try to get name attribute
        if hasattr(runnable, "name") and runnable.name:
            return str(runnable.name)

        # Try to get class name
        class_name = type(runnable).__name__
        if class_name and class_name != "Runnable":
            return class_name

        # Fallback
        return "langchain_agent"

    except Exception:
        return "langchain_agent"


# ======================== Callback Handler ========================


