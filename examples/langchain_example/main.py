import os
from typing import Optional

from dotenv import load_dotenv

# GATI observe
from gati import observe

# LangChain imports
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_openai import ChatOpenAI
from langchain.tools import tool


@tool
def multiply(a: float, b: float) -> float:
    """Multiply two numbers and return the product."""
    return a * b


def build_agent_with_llm(llm: ChatOpenAI) -> AgentExecutor:
    """Create an OpenAI-functions agent with one custom tool, using the provided LLM.

    Callbacks attached to the LLM will propagate through the agent and tools.
    """
    tools = [multiply]

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a helpful assistant. Use tools when helpful."),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )

    agent = create_openai_functions_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    return executor


def main() -> None:
    # Load environment variables from .env (for OPENAI_API_KEY)
    load_dotenv()

    # Sanity check for API key presence
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY not found. Create a .env with OPENAI_API_KEY=... or export it."
        )

    # GATI setup
    observe.init(backend_url="http://localhost:8000", agent_name="langchain_demo")
    print("GATI initialized")

    # Choose approach via env toggle APPROACH (A or B)
    approach = (os.getenv("GATI_LC_APPROACH") or "A").upper()

    # Common model
    selected_model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

    if approach == "A":
        # Approach A: Manual callbacks (recommended)
        llm = ChatOpenAI(
            model=selected_model,
            temperature=0,
            callbacks=observe.get_callbacks(),  # Explicit attachment
        )
        agent = build_agent_with_llm(llm)
    else:
        # Approach B: Auto-instrument (limited for LangChain 1.0+)
        observe.auto_instrument()  # May show warning on LangChain 1.0+
        llm = ChatOpenAI(model=selected_model, temperature=0)
        agent = build_agent_with_llm(llm)

    print("Running agent...")
    query = "What is 12 times 7? Use the multiply tool if needed."
    result = agent.invoke({"input": query})

    print("Agent output:")
    print(result)

    print("Done! Check dashboard at http://localhost:3000")


if __name__ == "__main__":
    main()


