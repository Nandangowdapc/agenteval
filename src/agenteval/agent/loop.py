"""Tool-calling loop: LLM -> tools -> LLM ... until the LLM answers without tools."""

from collections.abc import Callable

from langgraph.graph import END

from .graph import AgentGraph
from .state import AgentState
from .tools import ToolRegistry, tool_registry


def create_tool_node(registry: ToolRegistry = tool_registry):
    """Build a node that executes every tool call in the last assistant message."""

    def tool_node(state: AgentState) -> dict:
        last = state["messages"][-1]
        messages, results, errors = [], [], []
        for call in last.get("tool_calls", []):
            tool = registry.get(call["name"])
            if tool is None:
                output = f"Error: unknown tool '{call['name']}'"
                errors.append(output)
            else:
                try:
                    output = tool(**call["args"])
                except TypeError as e:
                    output = f"Error: bad arguments for '{call['name']}': {e}"
                    errors.append(output)
            messages.append(
                {"role": "tool", "tool_call_id": call["id"], "content": output}
            )
            results.append({"id": call["id"], "name": call["name"], "output": output})
        return {"messages": messages, "tool_results": results, "errors": errors}

    return tool_node


def create_router(max_steps: int) -> Callable[[AgentState], str]:
    """Route after the LLM: run tools if it asked for any, else finish."""

    def route(state: AgentState) -> str:
        last = state["messages"][-1] if state["messages"] else {}
        if not last.get("tool_calls"):
            return "end"
        if state["current_step"] >= max_steps:
            return "stop"
        return "tools"

    return route


def build_tool_agent(
    llm_node: Callable[[AgentState], dict],
    registry: ToolRegistry = tool_registry,
    max_steps: int = 10,
    name: str = "tool-agent",
) -> AgentGraph:
    """Wire llm -> (tools -> llm)* -> END, capped at max_steps LLM calls.

    If the cap is hit while the LLM still wants tools, the run ends with an
    entry in `errors` instead of looping forever.
    """

    def stop_node(state: AgentState) -> dict:
        return {"errors": [f"Stopped after {max_steps} steps with tool calls pending"]}

    graph = AgentGraph(name=name)
    graph.add_node("llm", llm_node)
    graph.add_node("tools", create_tool_node(registry))
    graph.add_node("stop", stop_node)
    graph.set_entry_point("llm")
    graph.add_conditional_edges(
        "llm", create_router(max_steps), {"tools": "tools", "stop": "stop", "end": END}
    )
    graph.add_edge("tools", "llm")
    graph.add_edge("stop", END)
    # Each loop is two LangGraph supersteps (llm + tools); leave headroom so our
    # own cap fires before LangGraph's GraphRecursionError.
    graph.recursion_limit = 2 * max_steps + 5
    return graph
