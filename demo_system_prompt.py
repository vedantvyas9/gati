#!/usr/bin/env python3
"""
Demo script showing system prompt tracking with GATI SDK.

This script demonstrates:
1. System prompt extraction from LangChain prompts
2. Automatic tracking with auto-injection
3. Backend transmission of all tracking data
"""

import os
from gati import observe
from gati.core.event import LLMCallEvent


def demo_basic_system_prompt():
    """Demo 1: Basic system prompt tracking."""
    print("\n" + "="*60)
    print("DEMO 1: Basic System Prompt Tracking")
    print("="*60)

    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate

    # Initialize GATI SDK with auto-injection
    observe.init(
        backend_url="http://localhost:8000",
        agent_name="demo-assistant",
        auto_inject=True  # Auto-inject callbacks
    )
    print("✓ GATI SDK initialized with auto-injection")

    # Create prompt with system message
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful math tutor. Always explain step by step."),
        ("human", "{question}")
    ])
    print("✓ Created prompt with system message")

    # Create LLM (no callbacks parameter needed due to auto-injection)
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
    print("✓ Created LLM (auto-injection enabled)")

    # Create chain
    chain = prompt | llm

    print("\n📤 Invoking chain...")
    print("   System: 'You are a helpful math tutor. Always explain step by step.'")
    print("   Human: 'What is 2+2?'")

    try:
        # Uncomment below to test with real API (requires OPENAI_API_KEY)
        # result = chain.invoke({"question": "What is 2+2?"})
        # print(f"\n📥 Response: {result.content}")

        print("\n✓ Would send to backend:")
        print("   - system_prompt: 'You are a helpful math tutor. Always explain step by step.'")
        print("   - prompt: 'What is 2+2?'")
        print("   - tokens_in: (counted)")
        print("   - tokens_out: (counted)")
        print("   - latency_ms: (measured)")
        print("   - cost: (calculated)")
    except Exception as e:
        print(f"   (Skipping real API call: {e})")

    # Force flush
    observe.flush()
    print("\n✓ Events flushed to backend")


def demo_multiple_system_messages():
    """Demo 2: Multiple system messages."""
    print("\n" + "="*60)
    print("DEMO 2: Multiple System Messages")
    print("="*60)

    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate

    observe.init(
        backend_url="http://localhost:8000",
        agent_name="multi-system-demo"
    )

    # Prompt with multiple system messages
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are helpful and concise."),
        ("system", "Always cite your sources."),
        ("system", "Use markdown formatting."),
        ("human", "{query}")
    ])
    print("✓ Created prompt with 3 system messages")

    print("\n✓ System messages will be concatenated:")
    print("   'You are helpful and concise.'")
    print("   'Always cite your sources.'")
    print("   'Use markdown formatting.'")
    print("\n   Sent as single system_prompt with \\n\\n separator")


def demo_event_structure():
    """Demo 3: Show event structure."""
    print("\n" + "="*60)
    print("DEMO 3: Event Structure")
    print("="*60)

    # Create a sample event
    event = LLMCallEvent(
        run_id="demo-run-123",
        model="gpt-4",
        prompt="What is the capital of France?",
        system_prompt="You are a geography expert. Always provide historical context.",
        completion="The capital of France is Paris.",
        tokens_in=25,
        tokens_out=12,
        latency_ms=234.5,
        cost=0.0015
    )

    print("\n✓ Sample LLMCallEvent created:")
    print(f"   run_id: {event.run_id}")
    print(f"   model: {event.model}")
    print(f"   system_prompt: {event.system_prompt}")
    print(f"   prompt: {event.prompt}")
    print(f"   completion: {event.completion}")
    print(f"   tokens_in: {event.tokens_in}")
    print(f"   tokens_out: {event.tokens_out}")
    print(f"   latency_ms: {event.latency_ms}")
    print(f"   cost: ${event.cost}")

    # Show serialized format
    event_dict = event.to_dict()
    print("\n✓ Serialized event (sent to backend):")
    import json
    print(json.dumps(event_dict, indent=2, default=str))


def demo_extraction_logic():
    """Demo 4: System prompt extraction from different formats."""
    print("\n" + "="*60)
    print("DEMO 4: System Prompt Extraction Logic")
    print("="*60)

    from gati.instrumentation.langchain import GatiLangChainCallback

    callback = GatiLangChainCallback()

    # Test 1: String prompts
    print("\n1️⃣  String prompts (no system message):")
    prompts = ["Tell me about Python programming."]
    system, user = callback._extract_system_and_user_prompts(prompts)
    print(f"   Input: {prompts}")
    print(f"   system_prompt: '{system}'")
    print(f"   prompt: '{user}'")

    # Test 2: Dict format
    print("\n2️⃣  Dict format (with system message):")
    prompts = [
        [
            {"role": "system", "content": "You are a Python expert."},
            {"role": "user", "content": "Explain decorators."}
        ]
    ]
    system, user = callback._extract_system_and_user_prompts(prompts)
    print(f"   Input: [dict messages]")
    print(f"   system_prompt: '{system}'")
    print(f"   prompt: '{user}'")

    # Test 3: Multiple system messages
    print("\n3️⃣  Multiple system messages:")
    prompts = [
        [
            {"role": "system", "content": "You are helpful."},
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "Hello"}
        ]
    ]
    system, user = callback._extract_system_and_user_prompts(prompts)
    print(f"   Input: [2 system + 1 user]")
    print(f"   system_prompt: '{system}'")
    print(f"   prompt: '{user}'")


def demo_backend_payload():
    """Demo 5: Show backend payload structure."""
    print("\n" + "="*60)
    print("DEMO 5: Backend Payload Structure")
    print("="*60)

    print("\n✓ Events are sent to backend as:")
    print("   Endpoint: POST /api/events")
    print("   Content-Type: application/json")

    payload = {
        "events": [
            {
                "event_type": "llm_call",
                "run_id": "abc-123",
                "event_id": "evt-xyz-789",
                "timestamp": "2025-01-15T10:30:00.123456",
                "agent_name": "my-agent",
                "model": "gpt-4",
                "prompt": "What is 2+2?",
                "system_prompt": "You are a math tutor.",
                "completion": "2+2 equals 4.",
                "tokens_in": 15,
                "tokens_out": 8,
                "latency_ms": 245.3,
                "cost": 0.0012,
                "parent_event_id": "evt-parent-456",
                "data": {
                    "status": "completed",
                    "system_prompt": "You are a math tutor.",
                    "lc_run_id": "lc-internal-123",
                    "tags": [],
                    "metadata": {}
                }
            }
        ]
    }

    import json
    print("\n" + json.dumps(payload, indent=2))


def main():
    """Run all demos."""
    print("\n" + "🚀"*30)
    print("GATI SDK - System Prompt Tracking Demo")
    print("🚀"*30)

    # Run demos
    demo_basic_system_prompt()
    demo_multiple_system_messages()
    demo_event_structure()
    demo_extraction_logic()
    demo_backend_payload()

    print("\n" + "="*60)
    print("✅ All demos completed!")
    print("="*60)

    print("\n📚 Next Steps:")
    print("   1. Set OPENAI_API_KEY environment variable")
    print("   2. Start your backend server on http://localhost:8000")
    print("   3. Run: python demo_system_prompt.py")
    print("   4. Check backend dashboard for tracked events")
    print("\n📖 Documentation: See SYSTEM_PROMPT_TRACKING.md")
    print("🧪 Tests: pytest tests/test_system_prompt_extraction.py -v")


if __name__ == "__main__":
    main()
