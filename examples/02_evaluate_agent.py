"""Evaluate an agent against a small suite of cases.

Uses a mock reasoning node so this runs without a GROQ_API_KEY. Swap
`mock_llm_node` for `create_llm_node()` from `agenteval.agent.llm` to
evaluate the real Groq-backed agent instead.
"""

import os
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langgraph.graph import END

from src.agenteval.agent.graph import AgentGraph
from src.agenteval.eval import EvalCase, Evaluator


def mock_llm_node(state):
    """Stand-in reasoning step: answers arithmetic tasks directly."""
    answer = str(eval(state["task"].rstrip("?").replace("What is", "").strip()))
    return {
        "messages": [{"role": "assistant", "content": answer}],
        "tool_calls": [{"name": "calculate"}],
        "current_step": state["current_step"] + 1,
    }


def evaluate_agent_example():
    print("=" * 60)
    print("AgentEval - Evaluation Example")
    print("=" * 60)

    graph = AgentGraph(name="mock-agent")
    graph.add_node("llm", mock_llm_node)
    graph.set_entry_point("llm")
    graph.add_edge("llm", END)

    cases = [
        EvalCase(
            task="What is 2 + 2?", expected_output="4", expected_tools=["calculate"]
        ),
        EvalCase(
            task="What is 10 + 5?", expected_output="15", expected_tools=["calculate"]
        ),
        EvalCase(
            task="What is 3 + 3?", expected_output="7", expected_tools=["calculate"]
        ),  # wrong on purpose
    ]

    report = Evaluator(graph).evaluate(cases)

    print("\nPer-case results:")
    for result in report.results:
        print(f"  [{result.overall:.2f}] {result.case.task!r} -> {result.scores}")

    print("\nSummary:")
    for name, value in report.summary().items():
        print(f"   {name}: {value:.2f}")

    print("=" * 60)


if __name__ == "__main__":
    evaluate_agent_example()
