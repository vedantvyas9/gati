"""Cost calculation utilities for LLM usage.

This module defines pricing information per model and helper functions to
normalize model names and compute estimated costs given input/output tokens.
"""

from __future__ import annotations

import logging
from typing import Dict


logger = logging.getLogger(__name__)


# Prices are in USD per 1,000,000 tokens (1M)
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    # OpenAI - GPT-4
    "gpt-4": {"input": 30.0, "output": 60.0},
    "gpt-4-32k": {"input": 60.0, "output": 120.0},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},

    # OpenAI - GPT-4o
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},

    # OpenAI - GPT-3.5 Turbo
    "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},

    # Anthropic Claude 3
    "claude-3-opus": {"input": 15.0, "output": 75.0},
    "claude-3-sonnet": {"input": 3.0, "output": 15.0},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},

    # Google Gemini
    "gemini-2-5-flash-lite": {"input": 0.1, "output": 0.4},
    "gemini-2-5-pro": {"input": 1.25, "output": 10.0},
    "gemini-pro": {"input": 0.5, "output": 1.5},

    # Add more models as needed
}


def normalize_model_name(model: str) -> str:
    """Normalize a raw model name to a canonical key used in MODEL_PRICING.

    Normalization rules:
    - Lowercase and strip whitespace
    - Handle common aliases and version suffices (e.g., "gpt-4-0613" -> "gpt-4")
    - Prefer stable family identifiers (e.g., any gpt-4-turbo* -> "gpt-4-turbo")
    """
    if not model:
        return ""

    name = model.strip().lower()

    # OpenAI GPT-4 families
    if name.startswith("gpt-4-turbo") or "gpt-4-turbo" in name:
        return "gpt-4-turbo"
    if name.startswith("gpt-4-32k") or "32k" in name:
        return "gpt-4-32k"
    if name.startswith("gpt-4") and "gpt-4o" not in name:  # Match gpt-4 but not gpt-4o
        return "gpt-4"

    # OpenAI GPT-4o families
    if "gpt-4o-mini" in name:
        return "gpt-4o-mini"
    if "gpt-4o" in name:
        return "gpt-4o"

    # OpenAI GPT-3.5 Turbo
    if name.startswith("gpt-3.5-turbo"):
        return "gpt-3.5-turbo"

    # Anthropic Claude 3 families
    if "claude-3-opus" in name:
        return "claude-3-opus"
    if "claude-3-sonnet" in name:
        return "claude-3-sonnet"
    if "claude-3-haiku" in name:
        return "claude-3-haiku"

    # Google Gemini families
    if "gemini" in name:
        if "2-5-pro" in name or "2.5-pro" in name:
            return "gemini-2-5-pro"
        if "2-5-flash-lite" in name or "2.5-flash-lite" in name:
            return "gemini-2-5-flash-lite"
        if "pro" in name:
            return "gemini-pro"

    # If there is a version-like suffix, try removing trailing tokens that look like
    # dates or preview markers (e.g., -0613, -1106-preview, -0125)
    # Fallback: strip everything after the third hyphen-separated token
    parts = name.split("-")
    if len(parts) > 3:
        simplified = "-".join(parts[:3])
        return simplified

    return name


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate dollar cost for a single LLM call.

    Args:
        model: Raw model name from provider
        input_tokens: Number of prompt/input tokens
        output_tokens: Number of completion/output tokens

    Returns:
        Estimated cost in USD, rounded to 6 decimal places (0.000001 = 1 millionth of a dollar).
        Returns 0.0 if the model is not recognized.
    """

    try:
        input_tokens_int = int(input_tokens or 0)
        output_tokens_int = int(output_tokens or 0)
    except (TypeError, ValueError):
        input_tokens_int = 0
        output_tokens_int = 0

    canonical = normalize_model_name(model)
    pricing = MODEL_PRICING.get(canonical)
    if not pricing:
        logger.warning("Unknown model for pricing: %s (normalized: %s)", model, canonical)
        return 0.0

    cost_in = (input_tokens_int / 1_000_000.0) * float(pricing.get("input", 0.0))
    cost_out = (output_tokens_int / 1_000_000.0) * float(pricing.get("output", 0.0))
    total = cost_in + cost_out
    return round(total, 6)


__all__ = [
    "MODEL_PRICING",
    "normalize_model_name",
    "calculate_cost",
]














