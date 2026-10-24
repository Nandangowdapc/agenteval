"""LLM inference node backed by a pluggable provider (Groq by default)."""

from .providers import PROVIDERS, create_chat_model
from .state import AgentState
from .tools import ToolRegistry

DEFAULT_MODEL = PROVIDERS["groq"].default_model

# Without this the model often answers arithmetic from memory, skipping the tool.
TOOL_SYSTEM_PROMPT = (
    "You have tools available. Always use a tool for arithmetic or lookups "
    "instead of answering from memory, then state the result."
)


def _total_tokens(response) -> list[int]:
    """Total tokens for one response as a 0/1-item list; empty if unreported."""
    usage = getattr(response, "usage_metadata", None)
    total = usage.get("total_tokens") if isinstance(usage, dict) else None
    if isinstance(total, bool) or not isinstance(total, int):
        return []
    return [total]


def create_llm_node(
    model: str | None = None,
    tools: ToolRegistry | None = None,
    system_prompt: str | None = None,
    provider: str | None = None,
):
    """Build a node function that calls an LLM for one reasoning step.

    `provider` is one of `PROVIDERS` (default: $AGENTEVAL_PROVIDER, else Groq);
    `model` defaults to that provider's agent model.
    With `tools`, the model may answer with tool calls instead of text; pair
    this node with `build_tool_agent` so those calls actually get executed.
    With `tools` and no `system_prompt`, a default nudging the model to use its
    tools is sent as a system message.
    """
    if system_prompt is None and tools is not None:
        system_prompt = TOOL_SYSTEM_PROMPT
    llm = create_chat_model(provider, model)
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
        if system_prompt:
            history.insert(0, {"role": "system", "content": system_prompt})
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
            "token_usage": _total_tokens(response),
            "current_step": state["current_step"] + 1,
        }

    return llm_node
