"""LangChain Callback Handler for GATI.

This module provides the GatiLangChainCallback handler that integrates with
LangChain's callback system to track LLM calls, tool executions, and chains.

The callback handler is automatically used by the auto-injection system, but
can also be used manually if needed.
"""

from __future__ import annotations

import time
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

# Try importing from latest LangChain structure
try:
    from langchain_core.callbacks import BaseCallbackHandler  # type: ignore
    from langchain_core.outputs import LLMResult  # type: ignore
    LANGCHAIN_AVAILABLE = True
except ImportError:
    try:
        # Fallback for older LangChain versions
        from langchain.callbacks.base import BaseCallbackHandler  # type: ignore
        from langchain.schema import LLMResult  # type: ignore
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

from gati.observe import observe
from gati.core.event import (
    LLMCallEvent,
    ToolCallEvent,
    AgentStartEvent,
    AgentEndEvent,
    StepEvent,
    generate_run_id,
    generate_run_name,
)
from gati.core.context import get_current_run_id, get_current_run_name, get_parent_event_id
from gati.utils.token_counter import extract_tokens_from_response
from gati.utils.cost_calculator import calculate_cost
from gati.utils.serializer import serialize

logger = logging.getLogger("gati")


class GatiLangChainCallback(BaseCallbackHandler):
    """GATI LangChain callback to automatically track key operations.

    Notes:
    - Supports both sync and async LangChain operations.
    - All logic is wrapped in try/except to ensure we never raise.
    - Timing is tracked per `run_id` using monotonic clocks.
    - Works seamlessly with LangChain 0.1.x, 0.2.x, and 1.0+
    """

    def __init__(self) -> None:
        super().__init__()
        # Timing stores keyed by run_id
        self._llm_start_times: Dict[str, float] = {}
        self._chain_start_times: Dict[str, float] = {}
        self._tool_start_times: Dict[str, float] = {}
        # Cache names keyed by run_id for chain/tool to enrich end events
        self._chain_names: Dict[str, str] = {}
        self._tool_names: Dict[str, str] = {}
        # Cache inputs and metadata for tools to enrich end events
        self._tool_inputs: Dict[str, Dict[str, Any]] = {}
        self._tool_metadata_cache: Dict[str, Dict[str, Any]] = {}
        # Mapping from LangChain run_id to GATI run_id
        self._run_id_mapping: Dict[str, str] = {}
        # Mapping from LangChain run_id to GATI event_id (for parent relationships)
        self._event_id_mapping: Dict[str, str] = {}
        # Streaming token accumulation keyed by run_id
        self._streaming_tokens: Dict[str, List[str]] = {}
        # Metadata caches for streaming
        self._streaming_metadata: Dict[str, Dict[str, Any]] = {}

    def _cleanup_run_mappings(self, lc_run_id: str) -> None:
        """Clean up all internal mappings for a completed LangChain run.

        This method removes entries from internal dictionaries to prevent memory leaks
        during long-running processes. It should be called when a LangChain run completes
        (either successfully or with an error).

        Args:
            lc_run_id: The LangChain run_id to clean up
        """
        if not lc_run_id:
            return

        try:
            # Remove from all internal dictionaries
            self._run_id_mapping.pop(lc_run_id, None)
            self._event_id_mapping.pop(lc_run_id, None)
            self._llm_start_times.pop(lc_run_id, None)
            self._chain_start_times.pop(lc_run_id, None)
            self._tool_start_times.pop(lc_run_id, None)
            self._chain_names.pop(lc_run_id, None)
            self._tool_names.pop(lc_run_id, None)
            self._tool_inputs.pop(lc_run_id, None)
            self._tool_metadata_cache.pop(lc_run_id, None)
            self._streaming_tokens.pop(lc_run_id, None)
            self._streaming_metadata.pop(lc_run_id, None)
        except Exception as e:
            # Fail-safe: log but don't raise
            logger.debug(f"Error cleaning up run mappings for {lc_run_id}: {e}")

    # ======================== LLM Callbacks ========================

    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> None:
        """Called when LLM starts execution."""
        try:
            # Get LangChain's internal run_id
            lc_run_id = self._safe_str(kwargs.get("run_id"))
            lc_parent_run_id = self._safe_str(kwargs.get("parent_run_id"))

            # Get GATI run_id and run_name from context (not LangChain's internal run_id)
            gati_run_id = get_current_run_id()
            gati_run_name = get_current_run_name()

            # If no GATI context, create a mapping for LangChain's run_id
            if not gati_run_name:
                # Check if parent has a GATI run_id mapping
                if lc_parent_run_id and lc_parent_run_id in self._run_id_mapping:
                    # Use parent's GATI run_id (all events in same LangChain execution share same run)
                    gati_run_name = self._run_id_mapping[lc_parent_run_id]
                elif lc_run_id in self._run_id_mapping:
                    # Already have a mapping for this LangChain run
                    gati_run_name = self._run_id_mapping[lc_run_id]
                else:
                    # Create new GATI run_id for this LangChain execution tree
                    from gati.core.event import generate_run_name
                    gati_run_name = generate_run_name()
                    self._run_id_mapping[lc_run_id] = gati_run_name

            # Store mapping if not already present
            if lc_run_id and lc_run_id not in self._run_id_mapping:
                self._run_id_mapping[lc_run_id] = gati_run_name

            # Store timing
            if lc_run_id:
                self._llm_start_times[lc_run_id] = time.monotonic()

            # Get parent event ID from context or from LangChain parent mapping
            parent_event_id = get_parent_event_id()
            if not parent_event_id and lc_parent_run_id:
                # Check if LangChain parent has a GATI event_id mapping
                parent_event_id = self._event_id_mapping.get(lc_parent_run_id)

            tags = kwargs.get("tags")
            metadata = kwargs.get("metadata")
            model_name = self._extract_model_name(serialized)

            # Extract system prompt and user prompt separately
            system_prompt, user_prompt = self._extract_system_and_user_prompts(prompts)

            # Fallback: if extraction failed, use the old method
            if not system_prompt and not user_prompt:
                user_prompt = self._join_prompts(prompts)

            # Extract additional metadata for debugging
            llm_metadata = self._extract_llm_metadata(serialized, kwargs)

            # Store prompts and metadata for use in on_llm_end
            # Don't create event yet to avoid duplicates
            if lc_run_id:
                self._streaming_metadata[lc_run_id] = {
                    "gati_run_name": gati_run_name,
                    "parent_event_id": parent_event_id,
                    "parent_run_id": lc_parent_run_id,
                    "tags": tags or [],
                    "metadata": metadata or {},
                    "model_name": model_name,
                    "user_prompt": user_prompt,
                    "system_prompt": system_prompt,
                    "serialized": self._safe_dict(serialized),
                    "llm_metadata": llm_metadata,
                }

            # Don't create event on start - only on end to avoid duplicates
        except Exception:
            # Fail-safe: never raise
            pass

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """Called when LLM completes successfully."""
        try:
            # Get LangChain's internal run_id for timing lookup
            lc_run_id = self._safe_str(kwargs.get("run_id"))
            lc_parent_run_id = self._safe_str(kwargs.get("parent_run_id"))

            # Get cached metadata from on_llm_start
            cached_metadata = self._streaming_metadata.get(lc_run_id, {})

            # Get GATI run_id from context or mapping
            gati_run_name = get_current_run_id()
            if not gati_run_name and lc_run_id:
                gati_run_name = self._run_id_mapping.get(lc_run_id, "")

            # Use cached gati_run_name if current one is missing
            if not gati_run_name and cached_metadata.get("gati_run_name"):
                gati_run_name = cached_metadata["gati_run_name"]

            # Get parent event ID from context or mapping
            parent_event_id = get_parent_event_id()
            if not parent_event_id and lc_parent_run_id:
                parent_event_id = self._event_id_mapping.get(lc_parent_run_id)

            # Use cached parent_event_id if current one is missing
            if not parent_event_id and cached_metadata.get("parent_event_id"):
                parent_event_id = cached_metadata["parent_event_id"]

            tags = kwargs.get("tags") or cached_metadata.get("tags", [])
            metadata = kwargs.get("metadata") or cached_metadata.get("metadata", {})

            # Extract model name with robust fallback
            model_name = self._extract_model_from_response(response)
            if not model_name:
                # Try using cached model name from on_llm_start
                model_name = cached_metadata.get("model_name", "")
            if not model_name:
                # Try extracting from serialized data if available
                serialized = kwargs.get("serialized", {}) or cached_metadata.get("serialized", {})
                model_name = self._extract_model_name(serialized)
                if not model_name:
                    logger.warning(
                        f"Failed to extract model name from LLM response for run {lc_run_id}. "
                        "Cost calculation may be inaccurate. Response type: {type(response).__name__}"
                    )

            # Extract completion text
            # First, check if we have streaming tokens accumulated
            completion_text = ""
            if lc_run_id in self._streaming_tokens:
                # Use accumulated streaming tokens
                completion_text = "".join(self._streaming_tokens[lc_run_id])
                logger.debug(f"Using {len(self._streaming_tokens[lc_run_id])} streaming tokens for completion")
            else:
                # Extract from response (non-streaming case)
                completion_text = self._extract_completion_text(response)
                if not completion_text:
                    logger.warning(
                        f"Failed to extract completion text from LLM response for run {lc_run_id}. "
                        f"Response type: {type(response).__name__}"
                    )

            # Extract token usage with multiple strategies
            tokens_in, tokens_out = self._tokens_from_generation_info(response)
            if tokens_in == 0 and tokens_out == 0:
                # Try the enhanced _extract_token_usage method
                tokens_in, tokens_out = self._extract_token_usage(response)

            # If still zero, try the utility extractor as final fallback
            if tokens_in == 0 and tokens_out == 0:
                usage = extract_tokens_from_response(response)
                tokens_in = int(usage.get("prompt_tokens", 0))
                tokens_out = int(usage.get("completion_tokens", 0))

            # Warn if token extraction failed
            if tokens_in == 0 and tokens_out == 0:
                logger.warning(
                    f"Failed to extract token usage from LLM response for run {lc_run_id}. "
                    f"Model: {model_name}, Response type: {type(response).__name__}. "
                    "This may result in inaccurate cost and usage metrics."
                )

            latency_ms = self._compute_latency_ms(self._llm_start_times, lc_run_id)
            cost = self._safe_cost(model_name, tokens_in, tokens_out)

            # Warn if cost calculation failed but we have tokens
            if cost == 0.0 and (tokens_in > 0 or tokens_out > 0) and model_name:
                logger.warning(
                    f"Cost calculation returned 0 for model {model_name} with {tokens_in} input tokens "
                    f"and {tokens_out} output tokens. Model may not be in cost database."
                )

            # Get prompts from cached metadata
            user_prompt = cached_metadata.get("user_prompt", "")
            system_prompt = cached_metadata.get("system_prompt", "")
            llm_metadata = cached_metadata.get("llm_metadata", {})

            event = LLMCallEvent(
                run_id=gati_run_name or "",
                run_name=gati_run_name or "",  # Use GATI run_name from context or mapping
                model=model_name,
                prompt=user_prompt,
                system_prompt=system_prompt,
                completion=completion_text,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency_ms,
                cost=cost,
                data={
                    "model": model_name,
                    "prompt": user_prompt,
                    "system_prompt": system_prompt,
                    "completion": completion_text,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "latency_ms": latency_ms,
                    "cost": cost,
                    "status": "completed",
                    "raw_llm_output": self._safe_dict(getattr(response, "llm_output", {}) or {}),
                    "lc_run_id": lc_run_id,  # Store LC run_id for reference
                    "parent_run_id": cached_metadata.get("parent_run_id", lc_parent_run_id),
                    "tags": tags,
                    "metadata": metadata,
                    "llm_metadata": llm_metadata,  # Additional debugging metadata
                },
            )

            # Set parent event ID if available
            if parent_event_id:
                event.parent_event_id = parent_event_id

            observe.track_event(event)
        except Exception as e:
            logger.error(f"Error in on_llm_end callback: {e}", exc_info=True)
        finally:
            # Cleanup timing entry, streaming tokens, and mappings
            if lc_run_id:
                self._llm_start_times.pop(lc_run_id, None)
                self._streaming_tokens.pop(lc_run_id, None)
                self._streaming_metadata.pop(lc_run_id, None)
                # Note: We keep run_id and event_id mappings for the duration of the callback
                # lifecycle in case they're needed by other events

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        """Called when LLM encounters an error."""
        try:
            run_id = self._safe_str(kwargs.get("run_id"))
            parent_run_id = self._safe_str(kwargs.get("parent_run_id"))
            tags = kwargs.get("tags")
            metadata = kwargs.get("metadata")
            latency_ms = self._compute_latency_ms(self._llm_start_times, run_id)

            event = LLMCallEvent(
                run_id=run_id,
                data={
                    "status": "error",
                    "error_type": type(error).__name__,
                    "error_message": self._safe_str(error),
                    "latency_ms": latency_ms,
                    "parent_run_id": parent_run_id,
                    "tags": tags or [],
                    "metadata": metadata or {},
                },
            )
            observe.track_event(event)
        except Exception:
            pass
        finally:
            if run_id and run_id in self._llm_start_times:
                self._llm_start_times.pop(run_id, None)
                self._streaming_tokens.pop(run_id, None)
                self._streaming_metadata.pop(run_id, None)

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Called when LLM streams a new token.

        This method accumulates tokens during streaming and will be used
        to construct the final completion when streaming ends.
        """
        try:
            lc_run_id = self._safe_str(kwargs.get("run_id"))
            if not lc_run_id:
                return

            # Initialize streaming token list if not present
            if lc_run_id not in self._streaming_tokens:
                self._streaming_tokens[lc_run_id] = []

            # Accumulate the token
            self._streaming_tokens[lc_run_id].append(token)

            # Store metadata for later use (on first token only)
            if lc_run_id not in self._streaming_metadata:
                lc_parent_run_id = self._safe_str(kwargs.get("parent_run_id"))
                tags = kwargs.get("tags")
                metadata = kwargs.get("metadata")

                # Get or create GATI run_id mapping
                gati_run_name = get_current_run_id()
                if not gati_run_name:
                    if lc_parent_run_id and lc_parent_run_id in self._run_id_mapping:
                        gati_run_name = self._run_id_mapping[lc_parent_run_id]
                    else:
                        gati_run_name = self._run_id_mapping.get(lc_run_id, "")

                self._streaming_metadata[lc_run_id] = {
                    "gati_run_name": gati_run_name,
                    "parent_run_id": lc_parent_run_id,
                    "tags": tags or [],
                    "metadata": metadata or {},
                }

                logger.debug(f"Started streaming for LLM run {lc_run_id}")

        except Exception as e:
            logger.debug(f"Error in on_llm_new_token: {e}")

    # ======================== Chain Callbacks ========================

    def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any) -> None:
        """Called when a chain starts execution."""
        try:
            run_id = self._safe_str(kwargs.get("run_id"))
            parent_run_id = self._safe_str(kwargs.get("parent_run_id"))
            tags = kwargs.get("tags")
            metadata = kwargs.get("metadata")
            chain_name = self._extract_chain_name(serialized)

            if run_id:
                self._chain_start_times[run_id] = time.monotonic()
                self._chain_names[run_id] = chain_name

            # Check if we're inside a GATI run context (LangGraph or manual tracking)
            current_gati_run_name = get_current_run_id()

            # Only create agent events if this is actually an agent chain
            if self._is_agent_chain(chain_name):
                event = AgentStartEvent(
                    run_id=run_id,
                    input=self._safe_dict(inputs),
                    metadata={
                        "chain_name": chain_name,
                        "serialized": self._safe_dict(serialized),
                        "parent_run_id": parent_run_id,
                        "tags": tags or [],
                        "metadata": metadata or {},
                    },
                )
                observe.track_event(event)
            # Don't create StepEvent for chains when inside a GATI run context
            # This avoids noise from intermediate chain components (prompts, parsers, etc.)
            # when executing inside LangGraph nodes or tracked agent runs
        except Exception:
            pass

    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        """Called when a chain completes successfully."""
        try:
            run_id = self._safe_str(kwargs.get("run_id"))
            parent_run_id = self._safe_str(kwargs.get("parent_run_id"))
            tags = kwargs.get("tags")
            metadata = kwargs.get("metadata")
            chain_name = self._chain_names.get(run_id, "")
            duration_ms = self._compute_latency_ms(self._chain_start_times, run_id)

            # Check if we're inside a GATI run context (LangGraph or manual tracking)
            current_gati_run_name = get_current_run_id()

            # Only create agent events if this is actually an agent chain
            if self._is_agent_chain(chain_name):
                event = AgentEndEvent(
                    run_id=run_id,
                    output=self._safe_dict(outputs),
                    total_duration_ms=duration_ms,
                )
                observe.track_event(event)
            # Don't create StepEvent for chains when inside a GATI run context
            # This avoids noise from intermediate chain components (prompts, parsers, etc.)
            # when executing inside LangGraph nodes or tracked agent runs
        except Exception:
            pass
        finally:
            # Clean up all mappings for this run to prevent memory leaks
            # Only cleanup for top-level chains (no parent) to avoid breaking nested chains
            if run_id:
                if not parent_run_id:
                    # This is a top-level chain, safe to cleanup all mappings
                    self._cleanup_run_mappings(run_id)
                else:
                    # This is a nested chain, only cleanup timing and name caches
                    self._chain_start_times.pop(run_id, None)
                    self._chain_names.pop(run_id, None)

    def on_chain_error(self, error: BaseException, **kwargs: Any) -> None:
        """Called when a chain encounters an error."""
        try:
            run_id = self._safe_str(kwargs.get("run_id"))
            parent_run_id = self._safe_str(kwargs.get("parent_run_id"))
            tags = kwargs.get("tags")
            metadata = kwargs.get("metadata")
            chain_name = self._chain_names.get(run_id, "")
            duration_ms = self._compute_latency_ms(self._chain_start_times, run_id)

            event = StepEvent(
                run_id=run_id,
                step_name=chain_name or "chain",
                duration_ms=duration_ms,
                metadata={
                    "status": "error",
                    "error_type": type(error).__name__,
                    "error_message": self._safe_str(error),
                    "parent_run_id": parent_run_id,
                    "tags": tags or [],
                    "metadata": metadata or {},
                },
            )
            observe.track_event(event)
        except Exception:
            pass
        finally:
            # Clean up all mappings for this run to prevent memory leaks
            # Only cleanup for top-level chains (no parent) to avoid breaking nested chains
            if run_id:
                if not parent_run_id:
                    # This is a top-level chain, safe to cleanup all mappings
                    self._cleanup_run_mappings(run_id)
                else:
                    # This is a nested chain, only cleanup timing and name caches
                    self._chain_start_times.pop(run_id, None)
                    self._chain_names.pop(run_id, None)

    # ======================== Tool Callbacks ========================

    def on_tool_start(self, tool: Any, input_str: str, **kwargs: Any) -> None:
        """Called when a tool starts execution."""
        try:
            # Get LangChain's internal run_id
            lc_run_id = self._safe_str(kwargs.get("run_id"))
            lc_parent_run_id = self._safe_str(kwargs.get("parent_run_id"))

            # Get GATI run_id from context or mapping
            gati_run_name = get_current_run_id()
            if not gati_run_name and lc_run_id:
                # Use existing mapping or create new one
                if lc_parent_run_id and lc_parent_run_id in self._run_id_mapping:
                    gati_run_name = self._run_id_mapping[lc_parent_run_id]
                else:
                    gati_run_name = self._run_id_mapping.get(lc_run_id, "")

            # Store mapping
            if lc_run_id and lc_run_id not in self._run_id_mapping and gati_run_name:
                self._run_id_mapping[lc_run_id] = gati_run_name

            # Get parent event ID from context or mapping
            parent_event_id = get_parent_event_id()
            if not parent_event_id and lc_parent_run_id:
                parent_event_id = self._event_id_mapping.get(lc_parent_run_id)

            tags = kwargs.get("tags")
            metadata = kwargs.get("metadata")
            tool_name = self._extract_tool_name(tool)

            # Extract additional tool metadata
            tool_metadata = self._extract_tool_metadata(tool, kwargs)

            if lc_run_id:
                self._tool_start_times[lc_run_id] = time.monotonic()
                self._tool_names[lc_run_id] = tool_name
                # Store input for later use in on_tool_end
                self._tool_inputs[lc_run_id] = {"input_str": self._safe_str(input_str)}
                self._tool_metadata_cache[lc_run_id] = {
                    "parent_event_id": parent_event_id,
                    "parent_run_id": lc_parent_run_id,
                    "tags": tags or [],
                    "metadata": metadata or {},
                    "tool_metadata": tool_metadata,
                }

            # Don't create event on start - only on end to avoid duplicates
        except Exception:
            pass

    def on_tool_end(self, output: Any, **kwargs: Any) -> None:
        """Called when a tool completes successfully."""
        try:
            # Get LangChain's internal run_id
            lc_run_id = self._safe_str(kwargs.get("run_id"))
            lc_parent_run_id = self._safe_str(kwargs.get("parent_run_id"))

            # Get GATI run_id from context or mapping
            gati_run_name = get_current_run_id()
            if not gati_run_name and lc_run_id:
                gati_run_name = self._run_id_mapping.get(lc_run_id, "")

            # Get parent event ID from context or mapping
            parent_event_id = get_parent_event_id()
            if not parent_event_id and lc_parent_run_id:
                parent_event_id = self._event_id_mapping.get(lc_parent_run_id)

            # Get stored input and metadata from on_tool_start
            tool_input = self._tool_inputs.get(lc_run_id, {})
            cached_metadata = self._tool_metadata_cache.get(lc_run_id, {})

            # Use cached parent_event_id if available and current one is missing
            if not parent_event_id and cached_metadata.get("parent_event_id"):
                parent_event_id = cached_metadata["parent_event_id"]

            tags = kwargs.get("tags") or cached_metadata.get("tags", [])
            metadata = kwargs.get("metadata") or cached_metadata.get("metadata", {})
            tool_name = self._tool_names.get(lc_run_id, "")
            latency_ms = self._compute_latency_ms(self._tool_start_times, lc_run_id)

            # Skip creating event if tool_name is missing
            # This filters out spurious tool callbacks from LangChain wrappers
            if not tool_name:
                logger.debug(f"Skipping tool event with no tool_name for run {lc_run_id}")
                return

            event = ToolCallEvent(
                run_id=gati_run_name or "",
                run_name=gati_run_name or "",
                tool_name=tool_name,
                input=tool_input,  # Use stored input from on_tool_start
                output={"output": self._safe_jsonable(output)},
                latency_ms=latency_ms,
                data={
                    "status": "completed",
                    "parent_run_id": cached_metadata.get("parent_run_id", lc_parent_run_id),
                    "tags": tags,
                    "metadata": metadata,
                    "tool_metadata": cached_metadata.get("tool_metadata", {}),
                },
            )

            # Set parent event ID if available
            if parent_event_id:
                event.parent_event_id = parent_event_id

            observe.track_event(event)
        except Exception:
            pass
        finally:
            if lc_run_id:
                self._tool_start_times.pop(lc_run_id, None)
                self._tool_names.pop(lc_run_id, None)
                self._tool_inputs.pop(lc_run_id, None)
                self._tool_metadata_cache.pop(lc_run_id, None)

    def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        """Called when a tool encounters an error."""
        try:
            run_id = self._safe_str(kwargs.get("run_id"))
            parent_run_id = self._safe_str(kwargs.get("parent_run_id"))
            tags = kwargs.get("tags")
            metadata = kwargs.get("metadata")
            tool_name = self._tool_names.get(run_id, "")
            latency_ms = self._compute_latency_ms(self._tool_start_times, run_id)

            event = ToolCallEvent(
                run_id=run_id,
                tool_name=tool_name,
                latency_ms=latency_ms,
                data={
                    "status": "error",
                    "error_type": type(error).__name__,
                    "error_message": self._safe_str(error),
                    "parent_run_id": parent_run_id,
                    "tags": tags or [],
                    "metadata": metadata or {},
                },
            )
            observe.track_event(event)
        except Exception:
            pass
        finally:
            if run_id:
                self._tool_start_times.pop(run_id, None)
                self._tool_names.pop(run_id, None)

    # ------------------------- Helpers -------------------------
    @staticmethod
    def _safe_str(value: Any) -> str:
        try:
            if value is None:
                return ""
            return str(value)
        except Exception:
            return ""

    @staticmethod
    def _safe_dict(value: Any) -> Dict[str, Any]:
        try:
            if isinstance(value, dict):
                return value
            # Attempt to coerce to dict if it exposes a dict-like interface
            if hasattr(value, "dict") and callable(getattr(value, "dict")):
                return dict(value.dict())  # type: ignore
            return {}
        except Exception:
            return {}

    @staticmethod
    def _safe_jsonable(value: Any) -> Any:
        try:
            # Primitive types or dict/list trees are fine
            if isinstance(value, (str, int, float, bool)):
                return value
            if isinstance(value, dict):
                return {str(k): GatiLangChainCallback._safe_jsonable(v) for k, v in value.items()}
            if isinstance(value, list):
                return [GatiLangChainCallback._safe_jsonable(v) for v in value]
            # Fallback to string representation
            return str(value)
        except Exception:
            return ""

    @staticmethod
    def _join_prompts(prompts: Optional[List[str]]) -> str:
        try:
            if not prompts:
                return ""
            return "\n\n".join([p for p in prompts if isinstance(p, str)])
        except Exception:
            return ""

    @staticmethod
    def _extract_system_and_user_prompts(prompts: Optional[List[Any]]) -> tuple[str, str]:
        """Extract system prompt and user prompt from LangChain prompts.

        Handles both string prompts and message-based prompts (ChatML format).

        Args:
            prompts: List of prompts (can be strings or message objects)

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        try:
            if not prompts:
                return "", ""

            system_parts = []
            user_parts = []

            for prompt in prompts:
                # Case 1: String prompt - treat as user prompt
                if isinstance(prompt, str):
                    user_parts.append(prompt)
                    continue

                # Case 2: Message list (ChatML format)
                # Check if prompt has messages attribute (ChatPromptTemplate, etc.)
                messages = None
                if hasattr(prompt, "messages"):
                    messages = getattr(prompt, "messages", [])
                elif hasattr(prompt, "to_messages") and callable(getattr(prompt, "to_messages")):
                    try:
                        messages = prompt.to_messages()
                    except Exception:
                        pass
                elif isinstance(prompt, list):
                    messages = prompt

                # Parse messages if we found them
                if messages:
                    for msg in messages:
                        # Handle different message types
                        msg_type = None
                        msg_content = None

                        # Try dict format first
                        if isinstance(msg, dict):
                            msg_type = msg.get("role") or msg.get("type")
                            msg_content = msg.get("content")
                        # Try object format
                        elif hasattr(msg, "type"):
                            msg_type = getattr(msg, "type", None)
                            msg_content = getattr(msg, "content", None)
                        elif hasattr(msg, "role"):
                            msg_type = getattr(msg, "role", None)
                            msg_content = getattr(msg, "content", None)
                        # Try __class__.__name__ as fallback
                        elif hasattr(msg, "__class__"):
                            class_name = msg.__class__.__name__.lower()
                            if "system" in class_name:
                                msg_type = "system"
                            elif "human" in class_name or "user" in class_name:
                                msg_type = "human"
                            elif "ai" in class_name or "assistant" in class_name:
                                msg_type = "ai"
                            msg_content = getattr(msg, "content", str(msg))

                        # Categorize message
                        if msg_type and msg_content:
                            msg_content_str = str(msg_content)
                            if msg_type.lower() in ("system",):
                                system_parts.append(msg_content_str)
                            elif msg_type.lower() in ("human", "user", "ai", "assistant"):
                                user_parts.append(msg_content_str)
                            else:
                                # Unknown type - add to user prompts
                                user_parts.append(msg_content_str)
                else:
                    # Not a recognized format - convert to string and add to user prompts
                    user_parts.append(str(prompt))

            system_prompt = "\n\n".join(system_parts) if system_parts else ""
            user_prompt = "\n\n".join(user_parts) if user_parts else ""

            return system_prompt, user_prompt

        except Exception:
            # Fallback to treating everything as user prompt
            try:
                return "", "\n\n".join([str(p) for p in (prompts or [])])
            except Exception:
                return "", ""

    @staticmethod
    def _extract_model_name(serialized: Dict[str, Any]) -> str:
        try:
            # Common patterns in LangChain serialized for LLMs
            name = serialized.get("name") or ""
            if name:
                return str(name)
            sid = serialized.get("id")
            if isinstance(sid, list) and sid:
                return str(sid[-1])
            if isinstance(sid, str):
                return sid.split(".")[-1]
        except Exception:
            pass
        return ""

    @staticmethod
    def _extract_model_from_response(response: Any) -> str:
        try:
            # Many LC integrations store the model name in llm_output["model" | "model_name"]
            llm_output = getattr(response, "llm_output", None) or {}
            if isinstance(llm_output, dict):
                for key in ("model", "model_name"):
                    if key in llm_output:
                        return str(llm_output[key])
        except Exception:
            pass
        return ""

    @staticmethod
    def _extract_completion_text(response: Any) -> str:
        """Extract completion text from LLM response with robust fallback logic.

        Tries multiple strategies to extract the completion text from various
        LangChain response formats to ensure compatibility across versions.
        """
        try:
            # Strategy 1: Standard generations path (most common)
            generations = getattr(response, "generations", None)
            if isinstance(generations, list) and generations:
                first = generations[0]
                if isinstance(first, list) and first:
                    gen = first[0]
                    # Try text attribute
                    text = getattr(gen, "text", None)
                    if isinstance(text, str) and text:
                        return text
                    # Try message.content for chat models
                    message = getattr(gen, "message", None)
                    if message:
                        content = getattr(message, "content", None)
                        if isinstance(content, str) and content:
                            return content

            # Strategy 2: Direct text attribute
            text = getattr(response, "text", None)
            if isinstance(text, str) and text:
                return text

            # Strategy 3: Output key in dict-like responses
            if hasattr(response, "get") and callable(getattr(response, "get")):
                output = response.get("output", None)
                if isinstance(output, str) and output:
                    return output

            # Strategy 4: Check llm_output for content
            llm_output = getattr(response, "llm_output", None)
            if isinstance(llm_output, dict):
                # Some providers store content in llm_output
                for key in ("content", "text", "completion"):
                    value = llm_output.get(key)
                    if isinstance(value, str) and value:
                        return value

            # Strategy 5: Try to extract from raw response if available
            if hasattr(response, "raw") or hasattr(response, "response"):
                raw = getattr(response, "raw", None) or getattr(response, "response", None)
                if raw:
                    if isinstance(raw, str):
                        return raw
                    # Try common keys in raw dict
                    if isinstance(raw, dict):
                        for key in ("content", "text", "completion", "message"):
                            value = raw.get(key)
                            if isinstance(value, str) and value:
                                return value
        except Exception as e:
            logger.debug(f"Error extracting completion text: {e}")

        return ""

    @staticmethod
    def _extract_token_usage(response: Any) -> tuple[int, int]:
        """Extract token usage from LLM response with robust fallback logic.

        Tries multiple strategies to extract token counts from various
        LangChain response formats and LLM providers.

        Returns:
            Tuple of (prompt_tokens, completion_tokens)
        """
        try:
            # Strategy 1: Check llm_output.token_usage or llm_output.usage (most common)
            llm_output = getattr(response, "llm_output", None)
            if isinstance(llm_output, dict):
                # Try both token_usage and usage keys
                usage = llm_output.get("token_usage") or llm_output.get("usage")
                if isinstance(usage, dict):
                    prompt_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
                    completion_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
                    if prompt_tokens > 0 or completion_tokens > 0:
                        return prompt_tokens, completion_tokens

            # Strategy 2: Check generation_info in first generation (common for newer versions)
            generations = getattr(response, "generations", None)
            if isinstance(generations, list) and generations:
                first = generations[0]
                if isinstance(first, list) and first:
                    gen = first[0]
                    gen_info = getattr(gen, "generation_info", None)
                    if isinstance(gen_info, dict):
                        # Try token_usage in generation_info
                        usage = gen_info.get("token_usage") or gen_info.get("usage")
                        if isinstance(usage, dict):
                            prompt_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
                            completion_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
                            if prompt_tokens > 0 or completion_tokens > 0:
                                return prompt_tokens, completion_tokens

                        # Some providers store tokens directly in generation_info
                        prompt_tokens = int(gen_info.get("prompt_tokens") or gen_info.get("input_tokens") or 0)
                        completion_tokens = int(gen_info.get("completion_tokens") or gen_info.get("output_tokens") or 0)
                        if prompt_tokens > 0 or completion_tokens > 0:
                            return prompt_tokens, completion_tokens

            # Strategy 3: Check response metadata or usage attribute
            if hasattr(response, "usage"):
                usage = getattr(response, "usage", None)
                if isinstance(usage, dict):
                    prompt_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
                    completion_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
                    if prompt_tokens > 0 or completion_tokens > 0:
                        return prompt_tokens, completion_tokens

            # Strategy 4: Check for direct token attributes (some providers)
            prompt_tokens = getattr(response, "prompt_tokens", None) or getattr(response, "input_tokens", None)
            completion_tokens = getattr(response, "completion_tokens", None) or getattr(response, "output_tokens", None)
            if prompt_tokens is not None or completion_tokens is not None:
                return int(prompt_tokens or 0), int(completion_tokens or 0)

            return 0, 0
        except Exception as e:
            logger.debug(f"Error extracting token usage: {e}")
            return 0, 0

    @staticmethod
    def _tokens_from_generation_info(response: Any) -> tuple[int, int]:
        try:
            gens = getattr(response, "generations", None)
            if isinstance(gens, list) and gens and isinstance(gens[0], list) and gens[0]:
                gen0 = gens[0][0]
                gi = getattr(gen0, "generation_info", None) or {}
                if isinstance(gi, dict):
                    usage = gi.get("token_usage") or {}
                    if isinstance(usage, dict):
                        return int(usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)), int(usage.get("completion_tokens", 0) or usage.get("output_tokens", 0))
        except Exception:
            pass
        return 0, 0

    @staticmethod
    def _extract_chain_name(serialized: Dict[str, Any]) -> str:
        try:
            name = serialized.get("name") or ""
            if name:
                return str(name)
            sid = serialized.get("id")
            if isinstance(sid, list) and sid:
                return str(sid[-1])
            if isinstance(sid, str):
                return sid.split(".")[-1]
        except Exception:
            pass
        return "chain"

    @staticmethod
    def _is_agent_chain(name: str) -> bool:
        try:
            return "agent" in (name or "").lower()
        except Exception:
            return False

    @staticmethod
    def _extract_tool_name(tool: Any) -> str:
        try:
            # LangChain tool has .name; fallback to class name or repr
            name = getattr(tool, "name", None)
            if isinstance(name, str) and name:
                return name
            cls_name = tool.__class__.__name__ if hasattr(tool, "__class__") else "tool"
            return str(cls_name)
        except Exception:
            return "tool"

    @staticmethod
    def _extract_llm_metadata(serialized: Dict[str, Any], kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Extract additional metadata from LLM for debugging purposes.

        Args:
            serialized: Serialized LLM information from LangChain
            kwargs: Additional kwargs from the callback

        Returns:
            Dictionary with metadata including class name, module, and config info
        """
        metadata = {}
        try:
            # Extract class/function name
            if "name" in serialized:
                metadata["class_name"] = str(serialized["name"])

            # Extract module name
            if "id" in serialized:
                sid = serialized["id"]
                if isinstance(sid, list):
                    metadata["module"] = ".".join([str(s) for s in sid[:-1]]) if len(sid) > 1 else ""
                    metadata["class_name"] = str(sid[-1]) if sid else ""
                elif isinstance(sid, str):
                    parts = sid.split(".")
                    metadata["module"] = ".".join(parts[:-1]) if len(parts) > 1 else ""
                    metadata["class_name"] = parts[-1] if parts else ""

            # Extract kwargs (model parameters, temperature, etc.)
            if "kwargs" in serialized:
                config_kwargs = serialized["kwargs"]
                if isinstance(config_kwargs, dict):
                    # Only include important config parameters (not secrets)
                    safe_keys = ["temperature", "max_tokens", "top_p", "top_k",
                                "frequency_penalty", "presence_penalty", "n", "stream"]
                    metadata["config"] = {
                        k: v for k, v in config_kwargs.items()
                        if k in safe_keys
                    }

            # Extract invocation config if present in kwargs
            invocation_params = kwargs.get("invocation_params")
            if invocation_params and isinstance(invocation_params, dict):
                metadata["invocation_params"] = {
                    k: v for k, v in invocation_params.items()
                    if k in ["temperature", "max_tokens", "stream"]
                }

        except Exception as e:
            logger.debug(f"Error extracting LLM metadata: {e}")

        return metadata

    @staticmethod
    def _extract_tool_metadata(tool: Any, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Extract additional metadata from tool for debugging purposes.

        Args:
            tool: The tool object
            kwargs: Additional kwargs from the callback

        Returns:
            Dictionary with metadata including class name, module, and description
        """
        metadata = {}
        try:
            # Extract class name
            if hasattr(tool, "__class__"):
                metadata["class_name"] = tool.__class__.__name__
                metadata["module"] = tool.__class__.__module__

            # Extract tool description if available
            if hasattr(tool, "description"):
                desc = getattr(tool, "description", None)
                if isinstance(desc, str):
                    metadata["description"] = desc[:200]  # Truncate long descriptions

            # Extract tool arguments schema if available
            if hasattr(tool, "args_schema"):
                args_schema = getattr(tool, "args_schema", None)
                if args_schema:
                    try:
                        # Try to get schema dict (for Pydantic models)
                        if hasattr(args_schema, "schema"):
                            schema_dict = args_schema.schema()
                            if isinstance(schema_dict, dict):
                                metadata["args_schema"] = {
                                    "properties": schema_dict.get("properties", {}),
                                    "required": schema_dict.get("required", []),
                                }
                    except Exception:
                        pass

            # Extract return_direct flag if available
            if hasattr(tool, "return_direct"):
                metadata["return_direct"] = bool(getattr(tool, "return_direct", False))

        except Exception as e:
            logger.debug(f"Error extracting tool metadata: {e}")

        return metadata

    @staticmethod
    def _compute_latency_ms(store: Dict[str, float], run_id: str) -> float:
        try:
            if not run_id or run_id not in store:
                return 0.0
            start = store.get(run_id, 0.0)
            if not start:
                return 0.0
            return max(0.0, (time.monotonic() - start) * 1000.0)
        except Exception:
            return 0.0

    @staticmethod
    def _safe_cost(model: str, tokens_in: int, tokens_out: int) -> float:
        try:
            return float(calculate_cost(model=model, input_tokens=tokens_in, output_tokens=tokens_out))
        except Exception:
            return 0.0


def _get_logger():
    try:
        from gati.utils import logger as gati_logger  # type: ignore

        return getattr(gati_logger, "logger", gati_logger)
    except Exception:
        import logging

        return logging.getLogger("gati")


def instrument_langchain() -> bool:
    """Attempt to register callbacks globally for older LangChain versions.

    Note: For LangChain 0.2+ and 1.0+, this function returns False and
    recommends using get_gati_callbacks() with explicit callback attachment.

    Returns:
        bool: True if global registration succeeded, False otherwise.
    """
    log = logging.getLogger("gati")
    try:
        # Attempt to use old global callback manager (LangChain < 0.1.x)
        try:
            from langchain.callbacks.manager import get_callback_manager  # type: ignore
        except ImportError:
            # Modern LangChain doesn't expose get_callback_manager
            log.info(
                "LangChain 0.2+ detected. Auto-instrumentation requires explicit callback attachment. "
                "Use: observe.get_callbacks() and pass to 'callbacks=' parameter."
            )
            return False

        # Try to register with the manager if it exists
        manager = get_callback_manager()
        handlers = getattr(manager, "handlers", [])

        # Check if already registered
        for handler in (handlers if isinstance(handlers, list) else []):
            if isinstance(handler, GatiLangChainCallback):
                return True

        # Try to add handler
        if hasattr(manager, "add_handler"):
            try:
                manager.add_handler(GatiLangChainCallback())
                log.info("Successfully registered GatiLangChainCallback globally")
                return True
            except Exception as e:
                log.debug(f"Failed to add handler globally: {e}")

        log.info(
            "LangChain 0.2+ detected. Auto-instrumentation requires explicit callback attachment. "
            "Use: observe.get_callbacks() and pass to 'callbacks=' parameter."
        )
        return False
    except Exception as e:
        log.debug(f"Global instrumentation failed: {e}")
        return False


def uninstrument_langchain() -> bool:
    """Remove previously registered GatiLangChainCallback from the global manager.

    Only applicable if instrument_langchain() was successful. Returns True if
    callback was removed or if nothing needed to be removed.

    Returns:
        bool: True on success, False on hard failure.
    """
    log = logging.getLogger("gati")
    try:
        try:
            from langchain.callbacks.manager import get_callback_manager  # type: ignore
        except ImportError:
            log.debug("LangChain callback manager unavailable; nothing to remove")
            return True

        manager = get_callback_manager()
        handlers = getattr(manager, "handlers", [])

        removed_any = False
        if isinstance(handlers, list):
            for handler in list(handlers):
                if isinstance(handler, GatiLangChainCallback):
                    try:
                        # Try remove_handler first (standard API)
                        if hasattr(manager, "remove_handler"):
                            manager.remove_handler(handler)  # type: ignore[attr-defined]
                            removed_any = True
                        # Try direct list removal as fallback
                        elif hasattr(handlers, "remove"):
                            handlers.remove(handler)
                            removed_any = True
                    except Exception as e:
                        log.debug(f"Failed to remove handler: {e}")

        if removed_any:
            log.info("Removed GatiLangChainCallback from LangChain global manager")
        else:
            log.debug("No GatiLangChainCallback registered; nothing to remove")
        return True
    except Exception as e:
        log.error(f"uninstrument_langchain failed: {e}")
        return False


def get_gati_callbacks() -> List[BaseCallbackHandler]:
    """Return a list containing a GatiLangChainCallback instance.

    This is the recommended way to attach GATI instrumentation to LangChain 0.2+
    and 1.0+ models and agents.

    Usage examples:

        # With individual LLM
        from langchain_openai import ChatOpenAI
        from gati import observe

        observe.init(backend_url="http://localhost:8000")
        llm = ChatOpenAI(model="gpt-3.5-turbo", callbacks=observe.get_callbacks())
        response = llm.invoke("Hello!")

        # With agent
        from langchain.agents import AgentExecutor, create_tool_calling_agent
        from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

        agent = create_tool_calling_agent(llm, tools, prompt)
        executor = AgentExecutor(agent=agent, tools=tools, callbacks=observe.get_callbacks())
        result = executor.invoke({"input": "What is 5 + 3?"})

    Returns:
        List[BaseCallbackHandler]: List containing GatiLangChainCallback instance
            (empty list if callback initialization fails, never raises).
    """
    try:
        return [GatiLangChainCallback()]
    except Exception as e:
        logging.getLogger("gati").debug(f"Failed to create GatiLangChainCallback: {e}")
        return []


def auto_add_callbacks(obj: Any) -> Any:
    """Attach GATI callbacks to an LLM/chain/agent instance if missing.

    Attempts to add GATI instrumentation callbacks to any LangChain object
    (LLM, Chain, Agent, etc.) that supports callbacks. This is a convenience
    function that handles both modern and legacy callback attachment patterns.

    Args:
        obj: A LangChain LLM, Chain, Agent, or other callback-compatible object.

    Returns:
        The same object (for chaining). Best-effort operation that never raises.

    Note:
        This function is a convenience and less reliable than explicitly passing
        callbacks=observe.get_callbacks() to the object's constructor or invocation.
    """
    try:
        cb = GatiLangChainCallback()

        # Modern pattern: callbacks attribute
        if hasattr(obj, "callbacks"):
            current = getattr(obj, "callbacks", None)
            if isinstance(current, list):
                # Only add if not already present
                if not any(isinstance(h, GatiLangChainCallback) for h in current):
                    current.append(cb)
            elif current is None:
                try:
                    setattr(obj, "callbacks", [cb])
                except Exception:
                    pass

        # Legacy pattern: callback_manager
        elif hasattr(obj, "callback_manager"):
            manager = getattr(obj, "callback_manager", None)
            if manager and hasattr(manager, "add_handler"):
                try:
                    manager.add_handler(cb)
                except Exception:
                    pass

        return obj
    except Exception as e:
        logging.getLogger("gati").debug(f"auto_add_callbacks failed: {e}")
        return obj

