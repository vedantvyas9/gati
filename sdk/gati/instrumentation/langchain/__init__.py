"""LangChain instrumentation for GATI.

This package provides automatic instrumentation for LangChain by combining:
1. Auto-injection: Monkey-patches Runnable methods to inject GATI callbacks
2. Callback handler: Tracks LLM calls, tool executions, and chain runs

Usage:
    from gati import observe

    # Initialize - auto-injection is enabled by default
    observe.init(backend_url="http://localhost:8000")

    # Use LangChain normally - everything is tracked!
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model="gpt-3.5-turbo")
    response = llm.invoke("Hello!")  # ← Automatically tracked!
"""

from gati.instrumentation.langchain.auto_inject import enable_auto_injection, disable_auto_injection
from gati.instrumentation.langchain.callback import GatiLangChainCallback, get_gati_callbacks

__all__ = [
    "enable_auto_injection",
    "disable_auto_injection",
    "GatiLangChainCallback",
    "get_gati_callbacks",
]
