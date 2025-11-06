"""Serialization utilities for converting complex Python and LangChain objects
to JSON-serializable structures safely.

Key features:
- Understands common LangChain types (LLM, Tool, Document, AgentAction/Finish, LLMResult)
- Handles circular references and recursion limiting
- Never raises on unknown types; falls back to string and logs a warning
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import logging
from typing import Any, Dict, Iterable, Mapping, MutableMapping, MutableSequence, Optional, Set


# Local logger for warnings/fallback; avoids depending on external logger util
logger = logging.getLogger("gati.serializer")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)


# Try multiple import paths to be compatible across LangChain versions
try:  # langchain-core >= 0.1
    from langchain_core.language_models import BaseLanguageModel as _BaseLanguageModel  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    _BaseLanguageModel = None  # type: ignore

try:
    from langchain_core.tools import BaseTool as _BaseTool  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    _BaseTool = None  # type: ignore

try:
    from langchain_core.documents import Document as _LCDocument  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    _LCDocument = None  # type: ignore

try:
    from langchain_core.agents import AgentAction as _AgentAction, AgentFinish as _AgentFinish  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    _AgentAction = None  # type: ignore
    _AgentFinish = None  # type: ignore

try:
    # Older versions
    from langchain.schema import LLMResult as _LLMResult  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    try:
        # Newer import
        from langchain_core.outputs import LLMResult as _LLMResult  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        _LLMResult = None  # type: ignore


def _is_primitive(value: Any) -> bool:
    return value is None or isinstance(value, (bool, int, float, str))


def _is_json_serializable(value: Any) -> bool:
    try:
        json.dumps(value)
        return True
    except Exception:
        return False


def _short_type_name(obj: Any) -> str:
    t = type(obj)
    return f"{t.__module__}.{t.__name__}"


def serialize_langchain_object(
    obj: Any,
    *,
    visited: Optional[Set[int]] = None,
    depth: int = 0,
    max_depth: int = 5,
) -> Any:
    """Best-effort serialization for LangChain objects to JSON-safe structures.

    Returns primitives where possible, otherwise dicts/lists with essential fields.
    Guards against circular references and deep recursion.
    """
    if visited is None:
        visited = set()

    if depth > max_depth:
        return "<max_depth>"

    if _is_primitive(obj):
        return obj

    obj_id = id(obj)
    if obj_id in visited:
        return "<circular>"
    visited.add(obj_id)

    # LangChain Document
    if _LCDocument is not None and isinstance(obj, _LCDocument):
        return {
            "type": "langchain.Document",
            "page_content": obj.page_content,
            "metadata": serialize(obj.metadata, visited=visited, depth=depth + 1, max_depth=max_depth),
        }

    # AgentAction
    if _AgentAction is not None and isinstance(obj, _AgentAction):
        return {
            "type": "langchain.AgentAction",
            "tool": getattr(obj, "tool", None),
            "tool_input": serialize(getattr(obj, "tool_input", None), visited=visited, depth=depth + 1, max_depth=max_depth),
            "log": getattr(obj, "log", None),
        }

    # AgentFinish
    if _AgentFinish is not None and isinstance(obj, _AgentFinish):
        return {
            "type": "langchain.AgentFinish",
            "return_values": serialize(getattr(obj, "return_values", None), visited=visited, depth=depth + 1, max_depth=max_depth),
            "log": getattr(obj, "log", None),
        }

    # LLMResult
    if _LLMResult is not None and isinstance(obj, _LLMResult):
        # generations is typically list[list[Generation]]; extract text safely
        safe_generations: Any = []
        try:
            for row in getattr(obj, "generations", []) or []:
                safe_row = []
                for gen in row or []:
                    # gen may have .text or .message
                    text = getattr(gen, "text", None)
                    if text is None and hasattr(gen, "message"):
                        text = getattr(getattr(gen, "message"), "content", None)
                    safe_row.append({"text": text})
                safe_generations.append(safe_row)
        except Exception:
            safe_generations = "<unavailable>"

        return {
            "type": "langchain.LLMResult",
            "generations": safe_generations,
            "llm_output": serialize(getattr(obj, "llm_output", None), visited=visited, depth=depth + 1, max_depth=max_depth),
        }

    # BaseTool
    if _BaseTool is not None and isinstance(obj, _BaseTool):
        data: Dict[str, Any] = {
            "type": "langchain.Tool",
            "name": getattr(obj, "name", None),
            "description": getattr(obj, "description", None),
        }
        # Try to capture schema/config where possible
        try:
            params = getattr(obj, "args_schema", None)
            if params is not None:
                data["args_schema"] = serialize(params.schema() if hasattr(params, "schema") else str(params), visited=visited, depth=depth + 1, max_depth=max_depth)
        except Exception:
            pass
        return data

    # BaseLanguageModel (incl. Chat models)
    if _BaseLanguageModel is not None and isinstance(obj, _BaseLanguageModel):
        fields: Dict[str, Any] = {}
        # Probe common attributes without dumping entire __dict__
        for attr in (
            "model_name",
            "model",
            "temperature",
            "max_tokens",
            "timeout",
            "streaming",
            "default_headers",
            "default_query",
        ):
            if hasattr(obj, attr):
                try:
                    fields[attr] = serialize(getattr(obj, attr), visited=visited, depth=depth + 1, max_depth=max_depth)
                except Exception:
                    fields[attr] = "<unavailable>"
        return {"type": "langchain.LanguageModel", **fields}

    # Fallback: not a known LangChain type → try generic serialization
    return serialize(obj, visited=visited, depth=depth, max_depth=max_depth)


def serialize(
    obj: Any,
    *,
    visited: Optional[Set[int]] = None,
    depth: int = 0,
    max_depth: int = 5,
) -> Any:
    """General-purpose safe serializer.

    - Preserves primitives
    - Serializes dataclasses
    - Walks dicts, lists, tuples, sets, and custom objects (via selected public attrs)
    - Protects against circular references and deep recursion
    - Never throws; on failure returns string representation and logs a warning
    """
    if visited is None:
        visited = set()

    try:
        if depth > max_depth:
            return "<max_depth>"

        if _is_primitive(obj):
            return obj

        # Pre-emptively try JSON directly
        if _is_json_serializable(obj):
            return obj

        obj_id = id(obj)
        if obj_id in visited:
            return "<circular>"
        visited.add(obj_id)

        # Handle bytes/bytearray
        if isinstance(obj, (bytes, bytearray)):
            try:
                return obj.decode("utf-8")
            except Exception:
                return "<bytes>"

        # Dataclasses
        if dataclasses.is_dataclass(obj):
            return {
                "__type__": _short_type_name(obj),
                **{
                    f.name: serialize(getattr(obj, f.name), visited=visited, depth=depth + 1, max_depth=max_depth)
                    for f in dataclasses.fields(obj)
                },
            }

        # Mappings
        if isinstance(obj, Mapping):
            return {
                serialize(k, visited=visited, depth=depth + 1, max_depth=max_depth): serialize(v, visited=visited, depth=depth + 1, max_depth=max_depth)
                for k, v in obj.items()
            }

        # Iterables (lists, tuples, sets, generators)
        if isinstance(obj, (list, tuple, set)) or (
            isinstance(obj, Iterable) and not isinstance(obj, (str, bytes, bytearray))
        ):
            try:
                return [
                    serialize(item, visited=visited, depth=depth + 1, max_depth=max_depth)
                    for item in list(obj)
                ]
            except Exception:
                # Some iterables are single-pass; fall back to string
                return str(obj)

        # Try LangChain-aware serializer for unknown objects
        lc_result = serialize_langchain_object(obj, visited=visited, depth=depth, max_depth=max_depth)
        if lc_result is not None:
            return lc_result

        # Generic objects: select a conservative set of public attributes
        public_attrs = [
            name
            for name in dir(obj)
            if not name.startswith("_") and not inspect.ismethod(getattr(obj, name, None)) and not inspect.isfunction(getattr(obj, name, None))
        ]

        data: Dict[str, Any] = {"__type__": _short_type_name(obj)}
        for name in public_attrs:
            # Skip very noisy attributes commonly found on external objects
            if name in {"__annotations__", "__dataclass_fields__"}:
                continue
            try:
                value = getattr(obj, name)
            except Exception:
                continue
            try:
                data[name] = serialize(value, visited=visited, depth=depth + 1, max_depth=max_depth)
            except Exception:
                data[name] = "<unavailable>"

        # If nothing meaningful, fall back to str
        if len(data) == 1:  # only __type__ present
            return str(obj)
        return data
    except Exception as exc:  # Last-resort safety net
        logger.warning("Failed to serialize %s: %s", _short_type_name(obj), exc)
        try:
            return str(obj)
        except Exception:
            return "<unserializable>"


__all__ = [
    "serialize",
    "serialize_langchain_object",
]


