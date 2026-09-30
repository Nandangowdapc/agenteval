"""LLM inference node backed by Groq."""

import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from .state import AgentState

load_dotenv()

DEFAULT_MODEL = "llama-3.3-70b-versatile"


def create_llm_node(model: str = DEFAULT_MODEL):
    """Build a node function that calls Groq for one reasoning step."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Copy .env.example to .env and add your key "
            "from https://console.groq.com/keys"
        )

    llm = ChatGroq(model=model, api_key=api_key)

    def llm_node(state: AgentState) -> dict:
        history = state["messages"] or [{"role": "user", "content": state["task"]}]
        response = llm.invoke(history)
        return {
            "messages": [{"role": "assistant", "content": response.content}],
            "current_step": state["current_step"] + 1,
        }

    return llm_node
