"""LLM inference node backed by Groq."""

import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from .state import AgentState
from .tools import ToolRegistry

load_dotenv()

DEFAULT_MODEL = "llama-3.3-70b-versatile"


def create_llm_node(model: str = DEFAULT_MODEL, tools: ToolRegistry | None = None):
    """Build a node function that calls Groq for one reasoning step.

    With `tools`, the model may answer with tool calls instead of text; pair
    this node with `build_tool_agent` so those calls actually get executed.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Copy .env.example to .env and add your key "
            "from https://console.groq.com/keys"
        )

    llm = ChatGroq(model=model, api_key=api_key)
    if tools is not None:
        llm = llm.bind_tools(
            [
                {"type": "function", "function": {"name": name, **schema}}
                for name, schema in tools.get_schema().items()
            ]
        )

    def llm_node(state: AgentState) -> dict:
        # The task isn't stored in `messages`, so prepend it on every call —
        # later steps need it alongside the tool results.
        history = [{"role": "user", "content": state["task"]}, *state["messages"]]
        response = llm.invoke(history)
        calls = [
            {"id": c["id"], "name": c["name"], "args": c["args"]}
            for c in response.tool_calls
        ]
        message = {"role": "assistant", "content": response.content}
        if calls:
            message["tool_calls"] = calls
        return {
            "messages": [message],
            "tool_calls": calls,
            "current_step": state["current_step"] + 1,
        }

    return llm_node
