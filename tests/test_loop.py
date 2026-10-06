"""Tests for the tool-calling loop (mock LLM nodes, no API key required)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langchain_core.messages import AIMessage

from src.agenteval.agent import llm as llm_module
from src.agenteval.agent.loop import build_tool_agent
from src.agenteval.agent.tools import tool_registry
from src.agenteval.eval import EvalCase, Evaluator


def tool_call(name, args, call_id="call_1"):
    return {"id": call_id, "name": name, "args": args}


def scripted_llm_node(script):
    """Mock LLM node that replays one scripted (content, tool_calls) per step."""

    def node(state):
        content, calls = script[min(state["current_step"], len(script) - 1)]
        message = {"role": "assistant", "content": content}
        if calls:
            message["tool_calls"] = calls
        return {
            "messages": [message],
            "tool_calls": calls,
            "current_step": state["current_step"] + 1,
        }

    return node


def test_loop_runs_tool_then_answers():
    node = scripted_llm_node(
        [("", [tool_call("calculate", {"expression": "17 * 23 + 4"})]), ("395", [])]
    )
    state = build_tool_agent(node).run("What is 17 * 23 + 4?")

    assert [m["role"] for m in state["messages"]] == ["assistant", "tool", "assistant"]
    assert state["messages"][1] == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": "395",
    }
    assert state["tool_results"][0]["output"] == "395"
    assert state["messages"][-1]["content"] == "395"
    assert state["current_step"] == 2
    assert state["errors"] == []


def test_loop_ends_immediately_without_tool_calls():
    state = build_tool_agent(scripted_llm_node([("hello", [])])).run("say hi")

    assert len(state["messages"]) == 1
    assert state["current_step"] == 1
    assert state["tool_results"] == []


def test_multiple_tool_calls_in_one_step():
    node = scripted_llm_node(
        [
            (
                "",
                [
                    tool_call("calculate", {"expression": "1 + 1"}, "a"),
                    tool_call("search", {"query": "langgraph"}, "b"),
                ],
            ),
            ("done", []),
        ]
    )
    state = build_tool_agent(node).run("two tools")

    tool_messages = [m for m in state["messages"] if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in tool_messages] == ["a", "b"]
    assert tool_messages[0]["content"] == "2"


def test_unknown_tool_is_reported_and_loop_continues():
    node = scripted_llm_node([("", [tool_call("teleport", {})]), ("sorry", [])])
    state = build_tool_agent(node).run("go")

    assert state["messages"][1]["content"] == "Error: unknown tool 'teleport'"
    assert state["errors"] == ["Error: unknown tool 'teleport'"]
    assert state["messages"][-1]["content"] == "sorry"


def test_bad_tool_arguments_are_reported():
    node = scripted_llm_node(
        [("", [tool_call("calculate", {"expr": "1 + 1"})]), ("oops", [])]
    )
    state = build_tool_agent(node).run("go")

    assert state["messages"][1]["content"].startswith("Error: bad arguments")
    assert len(state["errors"]) == 1


def test_max_steps_stops_an_endless_tool_loop():
    always_calls = scripted_llm_node(
        [("", [tool_call("calculate", {"expression": "1 + 1"})])]
    )
    state = build_tool_agent(always_calls, max_steps=3).run("loop forever")

    assert state["current_step"] == 3
    assert state["errors"] == ["Stopped after 3 steps with tool calls pending"]


def test_evaluator_scores_tool_agent():
    node = scripted_llm_node(
        [("", [tool_call("calculate", {"expression": "2 + 2"})]), ("4", [])]
    )
    report = Evaluator(build_tool_agent(node)).evaluate(
        [EvalCase(task="2 + 2?", expected_output="4", expected_tools=["calculate"])]
    )
    scores = report.results[0].scores

    assert scores["exact_match"] == 1.0
    assert scores["tool_call_accuracy"] == 1.0
    assert scores["success_rate"] == 1.0


# --- real llm_node logic, with ChatGroq swapped for a fake -----------------


class FakeChatGroq:
    """Stands in for ChatGroq: records inputs, replays scripted AIMessages."""

    def __init__(self, **kwargs):
        self.calls = []
        self.bound_tools = None
        self.responses = [
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "c1", "name": "calculate", "args": {"expression": "6 * 7"}}
                ],
            ),
            AIMessage(content="42"),
        ]

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self

    def invoke(self, history):
        self.calls.append(list(history))
        return self.responses[len(self.calls) - 1]


def test_groq_llm_node_with_tools(monkeypatch):
    fake = FakeChatGroq()
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(llm_module, "ChatGroq", lambda **kwargs: fake)

    node = llm_module.create_llm_node(tools=tool_registry)
    state = build_tool_agent(node).run("What is 6 * 7?")

    bound_names = {t["function"]["name"] for t in fake.bound_tools}
    assert bound_names == set(tool_registry.list_tools())
    # The task is resent on the second call, followed by the tool exchange
    assert fake.calls[1][0] == {"role": "user", "content": "What is 6 * 7?"}
    assert fake.calls[1][2] == {"role": "tool", "tool_call_id": "c1", "content": "42"}
    assert state["tool_calls"] == [
        {"id": "c1", "name": "calculate", "args": {"expression": "6 * 7"}}
    ]
    assert state["messages"][-1]["content"] == "42"
