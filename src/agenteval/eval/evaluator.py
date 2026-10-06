"""Run agent graphs against evaluation cases and score the results."""

from dataclasses import dataclass, field
from statistics import mean

from ..agent.graph import AgentGraph
from ..agent.state import AgentState
from . import metrics


@dataclass
class EvalCase:
    """A single evaluation case: a task and what a good run should look like."""

    task: str
    expected_output: str | None = None
    expected_tools: list[str] = field(default_factory=list)
    max_steps: int = 10


@dataclass
class EvalResult:
    """Scores for one case run through the agent."""

    case: EvalCase
    final_state: AgentState
    scores: dict[str, float]

    @property
    def overall(self) -> float:
        """Mean of all recorded scores for this case."""
        return mean(self.scores.values()) if self.scores else 0.0


@dataclass
class EvalReport:
    """Aggregated results across all cases in an evaluation run."""

    results: list[EvalResult]

    @property
    def overall(self) -> float:
        """Mean overall score across all cases."""
        return mean(r.overall for r in self.results) if self.results else 0.0

    def mean_score(self, metric_name: str) -> float:
        """Mean of a specific metric across cases that recorded it."""
        values = [
            r.scores[metric_name] for r in self.results if metric_name in r.scores
        ]
        return mean(values) if values else 0.0

    def summary(self) -> dict[str, float]:
        """Mean of every metric that appears in at least one result, plus overall."""
        names = {name for r in self.results for name in r.scores}
        summary = {name: self.mean_score(name) for name in sorted(names)}
        summary["overall"] = self.overall
        return summary


class Evaluator:
    """Runs an AgentGraph against a set of EvalCases and scores each run."""

    def __init__(self, graph: AgentGraph):
        self.graph = graph

    def evaluate_case(self, case: EvalCase) -> EvalResult:
        """Run the agent on one case and score the resulting state."""
        final_state = self.graph.run(case.task)
        scores: dict[str, float] = {}

        if case.expected_output is not None:
            output = (
                final_state["messages"][-1]["content"]
                if final_state["messages"]
                else ""
            )
            scores["exact_match"] = metrics.exact_match(output, case.expected_output)
            scores["contains_match"] = metrics.contains_match(
                output, case.expected_output
            )

        if case.expected_tools:
            called_tools = [tc["name"] for tc in final_state["tool_calls"]]
            scores["tool_call_accuracy"] = metrics.tool_call_accuracy(
                called_tools, case.expected_tools
            )

        scores["step_efficiency"] = metrics.step_efficiency(
            final_state["current_step"], case.max_steps
        )
        scores["success_rate"] = metrics.success_rate(final_state["errors"])

        return EvalResult(case=case, final_state=final_state, scores=scores)

    def evaluate(self, cases: list[EvalCase]) -> EvalReport:
        """Run the agent on every case and return an aggregated report."""
        return EvalReport(results=[self.evaluate_case(case) for case in cases])
