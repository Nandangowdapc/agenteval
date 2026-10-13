"""Tests for the evaluation framework."""

import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langgraph.graph import END

from src.agenteval.agent.graph import AgentGraph
from src.agenteval.eval import EvalCase, Evaluator, metrics


def mock_llm_node(state):
    """Deterministic stand-in for a real LLM node, no API key required."""
    return {
        "messages": [{"role": "assistant", "content": "4"}],
        "tool_calls": [{"name": "calculate"}],
        "current_step": state["current_step"] + 1,
    }


def build_mock_graph() -> AgentGraph:
    graph = AgentGraph(name="mock-agent")
    graph.add_node("llm", mock_llm_node)
    graph.set_entry_point("llm")
    graph.add_edge("llm", END)
    return graph


# --- metrics ---------------------------------------------------------------


def test_exact_match():
    assert metrics.exact_match("4", "4") == 1.0
    assert metrics.exact_match(" 4 ", "4") == 1.0
    assert metrics.exact_match("5", "4") == 0.0


def test_contains_match():
    assert metrics.contains_match("The answer is 4.", "4") == 1.0
    assert metrics.contains_match("The answer is five.", "4") == 0.0


def test_tool_call_accuracy():
    assert metrics.tool_call_accuracy(["calculate"], ["calculate"]) == 1.0
    assert metrics.tool_call_accuracy([], ["calculate", "search"]) == 0.0
    assert metrics.tool_call_accuracy(["calculate"], []) == 1.0


def test_step_efficiency():
    assert metrics.step_efficiency(1, 5) == 1.0
    assert metrics.step_efficiency(5, 5) == 0.0
    assert metrics.step_efficiency(1, 1) == 1.0


def test_success_rate():
    assert metrics.success_rate([]) == 1.0
    assert metrics.success_rate(["boom"]) == 0.0


def test_latency_score():
    assert metrics.latency_score(0.0, 2.0) == 1.0
    assert metrics.latency_score(1.0, 2.0) == 0.5
    assert metrics.latency_score(2.0, 2.0) == 0.0
    assert metrics.latency_score(5.0, 2.0) == 0.0
    assert metrics.latency_score(0.0, 0.0) == 1.0
    assert metrics.latency_score(1.0, 0.0) == 0.0


def test_token_efficiency():
    assert metrics.token_efficiency(0, 100) == 1.0
    assert metrics.token_efficiency(50, 100) == 0.5
    assert metrics.token_efficiency(100, 100) == 0.0
    assert metrics.token_efficiency(500, 100) == 0.0
    assert metrics.token_efficiency(0, 0) == 1.0
    assert metrics.token_efficiency(1, 0) == 0.0


# --- evaluator ---------------------------------------------------------------


def test_evaluate_case_scores():
    evaluator = Evaluator(build_mock_graph())
    case = EvalCase(
        task="What is 2 + 2?",
        expected_output="4",
        expected_tools=["calculate"],
        max_steps=5,
    )

    result = evaluator.evaluate_case(case)

    assert result.scores["exact_match"] == 1.0
    assert result.scores["contains_match"] == 1.0
    assert result.scores["tool_call_accuracy"] == 1.0
    assert result.scores["step_efficiency"] == 1.0
    assert result.scores["success_rate"] == 1.0
    assert result.overall == 1.0


def test_evaluate_report_summary():
    evaluator = Evaluator(build_mock_graph())
    cases = [
        EvalCase(task="What is 2 + 2?", expected_output="4"),
        EvalCase(task="What is 2 + 3?", expected_output="5"),
    ]

    report = evaluator.evaluate(cases)

    assert len(report.results) == 2
    assert report.mean_score("exact_match") == 0.5
    summary = report.summary()
    assert "exact_match" in summary
    assert "overall" in summary


def test_evaluate_case_latency():
    evaluator = Evaluator(build_mock_graph())

    # No budget -> no latency score, but timing is still recorded.
    result = evaluator.evaluate_case(EvalCase(task="What is 2 + 2?"))
    assert "latency_score" not in result.scores
    assert result.elapsed_seconds >= 0.0

    generous = evaluator.evaluate_case(
        EvalCase(task="What is 2 + 2?", max_latency_seconds=60.0)
    )
    assert 0.9 < generous.scores["latency_score"] <= 1.0

    # A zero budget can never be met by a run that takes measurable time.
    tight = evaluator.evaluate_case(
        EvalCase(task="What is 2 + 2?", max_latency_seconds=0.0)
    )
    assert tight.scores["latency_score"] == 0.0


def test_report_elapsed_aggregates():
    report = Evaluator(build_mock_graph()).evaluate(
        [EvalCase(task="a"), EvalCase(task="b")]
    )
    assert report.total_elapsed_seconds == sum(
        r.elapsed_seconds for r in report.results
    )
    assert report.mean_elapsed_seconds == report.total_elapsed_seconds / 2
