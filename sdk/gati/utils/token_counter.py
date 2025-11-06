"""Token counting utilities with graceful fallbacks.

This module provides helper functions to count tokens for given text and to
estimate tokens for ChatML-style message lists. It uses tiktoken when
available and falls back to a rough heuristic otherwise.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Any


logger = logging.getLogger(__name__)

# Cache encodings at module level for performance
_ENCODING_CACHE: Dict[str, Any] = {}

try:
    import tiktoken  # type: ignore
except Exception:  # pragma: no cover - environment without tiktoken
    tiktoken = None  # type: ignore


def _get_encoding(model: str) -> Any:
    """Get (and cache) a tiktoken encoding for a given model name.

    Unknown models fall back to the cl100k_base encoding.
    """
    global _ENCODING_CACHE
    if not tiktoken:
        return None

    key = (model or "").strip() or "gpt-3.5-turbo"
    if key in _ENCODING_CACHE:
        return _ENCODING_CACHE[key]

    try:
        enc = tiktoken.encoding_for_model(key)
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")

    _ENCODING_CACHE[key] = enc
    return enc


def count_tokens(text: str | None, model: str = "gpt-3.5-turbo") -> int:
    """Count tokens for a given text using tiktoken when available.

    Returns 0 for None/empty input. Falls back to len(text)/4 heuristic if
    tiktoken is unavailable or encoding fails.
    """
    if not text:
        return 0

    if not tiktoken:
        # Rough rule of thumb: ~4 chars per token for English text
        return int(len(text) / 4)

    try:
        encoding = _get_encoding(model)
        if encoding is None:
            return int(len(text) / 4)
        tokens = encoding.encode(text)
        return len(tokens)
    except Exception as exc:  # be defensive against encoding quirks
        logger.debug("tiktoken failed to encode text: %s", exc)
        return int(len(text) / 4)


def estimate_tokens_from_messages(messages: List[Dict[str, Any]] | None, model: str = "gpt-3.5-turbo") -> int:
    """Estimate total tokens for a list of ChatML messages.

    We account for a formatting overhead of ~4 tokens per message and sum the
    tokens in the commonly used fields (role, content, name). This is an
    approximation suitable for cost estimation.
    """
    if not messages:
        return 0

    total = 0
    for msg in messages:
        if not isinstance(msg, dict):
            continue

        # Base overhead per message (approximation)
        total += 4

        # Common fields in ChatML
        role = msg.get("role")
        content = msg.get("content")
        name = msg.get("name")

        if role:
            total += count_tokens(str(role), model=model)
        if content:
            # content might be a list of dicts for tool messages; coerce to str
            total += count_tokens(str(content), model=model)
        if name:
            total += count_tokens(str(name), model=model)

    return total


def estimate_tokens_fallback(text: str) -> int:
    """Return a rough token estimate when provider usage is missing.

    Rough estimate - 4 chars ≈ 1 token
    """
    if not text:
        return 0
    return len(text) // 4


def _safe_get(obj: Any, *path: str) -> Any:
    """Safely access nested attributes/keys along a path.

    Works with dicts or objects; falls back to __dict__ when present.
    Returns None if any intermediate node is missing.
    """
    current = obj
    for key in path:
        if current is None:
            return None
        try:
            if isinstance(current, dict):
                current = current.get(key)
                continue
            if hasattr(current, key):
                current = getattr(current, key)
                continue
            d = getattr(current, "__dict__", None)
            if isinstance(d, dict):
                current = d.get(key)
                continue
            return None
        except Exception:
            return None
    return current


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def extract_tokens_from_response(response: Any, provider: str = "auto") -> Dict[str, int]:
    """Extract token usage across providers in a provider-agnostic way.

    Returns a dict: {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}

    Supported formats:
    - OpenAI / Azure OpenAI:
      response.usage.prompt_tokens, response.usage.completion_tokens, response.usage.total_tokens

    - Anthropic:
      response.usage.input_tokens → prompt_tokens, response.usage.output_tokens → completion_tokens

    - Cohere:
      response.meta.billed_units.input_tokens, response.meta.billed_units.output_tokens

    - Google (Vertex AI):
      response.usage_metadata.prompt_token_count, response.usage_metadata.candidates_token_count

    - Bedrock (AWS):
      response["usage"]["inputTokens"], response["usage"]["outputTokens"]

    - Replicate:
      response.metrics.input_token_count, response.metrics.output_token_count

    Additional handling:
    - Dict responses and object responses
    - Nested formats via __dict__
    - LangChain LLMResult via response.llm_output.token_usage/usage

    Auto-detection order (when provider="auto"): OpenAI → Anthropic → Bedrock → Google → Cohere → Replicate.
    Class name hints (e.g., ChatCompletion/Message/GenerateContentResponse) are used to prioritize likely providers.
    """
    def _result(prompt: int = 0, completion: int = 0, total: int | None = None) -> Dict[str, int]:
        if total is None:
            total = (prompt or 0) + (completion or 0)
        return {
            "prompt_tokens": _to_int(prompt, 0),
            "completion_tokens": _to_int(completion, 0),
            "total_tokens": _to_int(total, 0),
        }

    try:
        if response is None:
            return _result()

        # LangChain LLMResult shortcut
        llm_output = _safe_get(response, "llm_output")
        if isinstance(llm_output, dict):
            usage = llm_output.get("token_usage") or llm_output.get("usage") or {}
            if isinstance(usage, dict):
                prompt = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
                completion = usage.get("completion_tokens") or usage.get("output_tokens") or 0
                return _result(prompt, completion)
            # some wrappers surface direct counts
            prompt = llm_output.get("prompt_tokens", 0)
            completion = llm_output.get("completion_tokens", 0)
            if prompt or completion:
                return _result(prompt, completion)

        # Provider hints via class name
        cls_name = getattr(response, "__class__", type(response)).__name__
        lower_cls = (cls_name or "").lower()
        hinted: List[str] = []
        if "chatcompletion" in lower_cls or "completion" in lower_cls:
            hinted.append("openai")
        if cls_name == "Message" or "anthropic" in lower_cls:
            hinted.append("anthropic")
        if "generatecontentresponse" in lower_cls or "vertex" in lower_cls:
            hinted.append("google")

        base_order: List[str] = ["openai", "anthropic", "bedrock", "google", "cohere", "replicate"]
        if provider and provider != "auto":
            try_order = [provider.lower()]
        else:
            try_order = []
            for name in hinted + base_order:
                if name not in try_order:
                    try_order.append(name)

        # Provider extractors
        def _openai(obj: Any) -> Dict[str, int] | None:
            usage = _safe_get(obj, "usage")
            if usage is not None:
                p = _safe_get(usage, "prompt_tokens")
                c = _safe_get(usage, "completion_tokens")
                t = _safe_get(usage, "total_tokens")
                if any(v is not None for v in (p, c, t)):
                    return _result(p or 0, c or 0, t)
            return None

        def _anthropic(obj: Any) -> Dict[str, int] | None:
            usage = _safe_get(obj, "usage")
            if usage is not None:
                p = _safe_get(usage, "input_tokens")
                c = _safe_get(usage, "output_tokens")
                if p is not None or c is not None:
                    return _result(p or 0, c or 0)
            return None

        def _bedrock(obj: Any) -> Dict[str, int] | None:
            usage = None
            if isinstance(obj, dict):
                usage = obj.get("usage")
            if usage is None:
                usage = _safe_get(obj, "usage")
            if isinstance(usage, dict):
                p = usage.get("inputTokens")
                c = usage.get("outputTokens")
                if p is not None or c is not None:
                    return _result(p or 0, c or 0)
            return None

        def _google(obj: Any) -> Dict[str, int] | None:
            meta = _safe_get(obj, "usage_metadata")
            if meta is not None:
                p = _safe_get(meta, "prompt_token_count")
                c = _safe_get(meta, "candidates_token_count")
                if p is not None or c is not None:
                    return _result(p or 0, c or 0)
            return None

        def _cohere(obj: Any) -> Dict[str, int] | None:
            meta = _safe_get(obj, "meta")
            billed = _safe_get(meta, "billed_units") if meta is not None else None
            if billed is not None:
                p = _safe_get(billed, "input_tokens")
                c = _safe_get(billed, "output_tokens")
                if p is not None or c is not None:
                    return _result(p or 0, c or 0)
            return None

        def _replicate(obj: Any) -> Dict[str, int] | None:
            metrics = _safe_get(obj, "metrics")
            if metrics is not None:
                p = _safe_get(metrics, "input_token_count")
                c = _safe_get(metrics, "output_token_count")
                if p is not None or c is not None:
                    return _result(p or 0, c or 0)
            return None

        handlers = {
            "openai": _openai,       # also Azure OpenAI
            "anthropic": _anthropic,
            "bedrock": _bedrock,
            "google": _google,
            "cohere": _cohere,
            "replicate": _replicate,
        }

        for name in try_order:
            fn = handlers.get(name)
            if not fn:
                continue
            try:
                out = fn(response)
                if out:
                    return out
            except Exception:
                # keep trying others
                continue

        # Generic usage dict last chance
        usage = _safe_get(response, "usage")
        if isinstance(usage, dict):
            p = usage.get("prompt_tokens") or usage.get("input_tokens") or usage.get("inputTokens") or 0
            c = usage.get("completion_tokens") or usage.get("output_tokens") or usage.get("outputTokens") or 0
            t = usage.get("total_tokens")
            if p or c or t:
                return _result(p, c, t)

        logger.warning(
            "Token usage not found (provider=%s, type=%s)",
            provider,
            getattr(response, "__class__", type(response)).__name__,
        )
        return _result()

    except Exception as exc:
        logger.warning("Failed to extract tokens: %s", exc)
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


__all__ = [
    "count_tokens",
    "estimate_tokens_from_messages",
    "estimate_tokens_fallback",
    "extract_tokens_from_response",
]


