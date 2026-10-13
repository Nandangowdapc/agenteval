"""Load EvalCase suites from JSON/YAML files and run them from the command line.

Suite file shape (JSON or YAML)::

    {"name": "optional", "cases": [
        {"task": "What is 2 + 2?", "expected_output": "4",
         "expected_tools": ["calculate"], "max_steps": 5}
    ]}

A bare top-level list of cases is also accepted.

CLI::

    python -m agenteval.eval.suite examples/suite_arithmetic.json [--node mock|groq]
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from .evaluator import EvalCase, EvalReport, Evaluator

_CASE_FIELDS = {"task", "expected_output", "expected_tools", "max_steps"}


class SuiteError(ValueError):
    """Raised when a suite file is missing, unparseable, or invalid."""


def _parse_file(path: Path) -> Any:
    suffix = path.suffix.lower()
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SuiteError(f"Suite file not found: {path}") from None
    except OSError as exc:
        raise SuiteError(f"Cannot read suite file {path}: {exc}") from exc

    if suffix == ".json":
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise SuiteError(f"{path}: invalid JSON: {exc}") from exc
    if suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError:
            raise SuiteError(
                f"{path}: YAML needs pyyaml (pip install pyyaml); use JSON instead"
            ) from None
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise SuiteError(f"{path}: invalid YAML: {exc}") from exc
    raise SuiteError(f"{path}: unsupported extension {suffix!r} (.json, .yaml, .yml)")


def _build_case(raw: Any, where: str) -> EvalCase:
    if not isinstance(raw, dict):
        raise SuiteError(f"{where}: must be an object, got {type(raw).__name__}")
    unknown = set(raw) - _CASE_FIELDS
    if unknown:
        raise SuiteError(
            f"{where}: unknown field(s) {sorted(unknown)}; "
            f"allowed: {sorted(_CASE_FIELDS)}"
        )
    task = raw.get("task")
    if not isinstance(task, str) or not task.strip():
        raise SuiteError(f"{where}: 'task' is required and must be a non-empty string")

    kwargs: dict[str, Any] = {"task": task}
    if raw.get("expected_output") is not None:
        if not isinstance(raw["expected_output"], str):
            raise SuiteError(f"{where}: 'expected_output' must be a string")
        kwargs["expected_output"] = raw["expected_output"]
    if "expected_tools" in raw:
        tools = raw["expected_tools"]
        if not isinstance(tools, list) or not all(isinstance(t, str) for t in tools):
            raise SuiteError(f"{where}: 'expected_tools' must be a list of strings")
        kwargs["expected_tools"] = list(tools)
    if "max_steps" in raw:
        steps = raw["max_steps"]
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
            raise SuiteError(f"{where}: 'max_steps' must be a positive integer")
        kwargs["max_steps"] = steps
    return EvalCase(**kwargs)


def load_suite(path: str | Path) -> list[EvalCase]:
    """Load and validate a suite file, returning its EvalCases.

    Raises SuiteError with a message naming the file and the offending case.
    """
    path = Path(path)
    data = _parse_file(path)
    if isinstance(data, dict):
        if "cases" not in data:
            raise SuiteError(f"{path}: top-level object must have a 'cases' list")
        extra = set(data) - {"cases", "name", "description"}
        if extra:
            raise SuiteError(f"{path}: unknown top-level key(s) {sorted(extra)}")
        data = data["cases"]
    if not isinstance(data, list):
        raise SuiteError(f"{path}: expected a list of cases or an object with 'cases'")
    if not data:
        raise SuiteError(f"{path}: suite contains no cases")
    return [_build_case(raw, f"{path}: case #{i}") for i, raw in enumerate(data, 1)]


def _mock_llm_node(state):
    """Stand-in node: answers 'What is <expr>?' tasks via the safe calculator."""
    from ..agent.tools import tool_registry

    match = re.search(r"what is\s+(.+?)\??\s*$", state["task"], re.IGNORECASE)
    answer = tool_registry.get("calculate")(expression=match.group(1)) if match else ""
    return {
        "messages": [{"role": "assistant", "content": answer}],
        "tool_calls": [{"name": "calculate"}] if match else [],
        "current_step": state["current_step"] + 1,
    }


def build_graph(node: str):
    """Build the agent graph for the CLI: 'mock' (no key) or 'groq' (real LLM)."""
    from langgraph.graph import END

    from ..agent.graph import AgentGraph

    if node == "groq":
        from ..agent.llm import create_llm_node
        from ..agent.loop import build_tool_agent
        from ..agent.tools import tool_registry

        return build_tool_agent(create_llm_node(tools=tool_registry), tool_registry)
    graph = AgentGraph(name="mock-agent")
    graph.add_node("llm", _mock_llm_node)
    graph.set_entry_point("llm")
    graph.add_edge("llm", END)
    return graph


def format_report(report: EvalReport) -> str:
    lines = [f"[{r.overall:.2f}] {r.case.task!r} -> {r.scores}" for r in report.results]
    lines.append("Summary:")
    lines.extend(f"  {k}: {v:.2f}" for k, v in report.summary().items())
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an EvalCase suite file.")
    parser.add_argument("path", help="suite file (.json, .yaml, .yml)")
    parser.add_argument(
        "--node",
        choices=["mock", "groq"],
        default="mock",
        help="mock needs no API key; groq needs GROQ_API_KEY (default: mock)",
    )
    args = parser.parse_args(argv)

    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        cases = load_suite(args.path)
    except SuiteError as exc:
        print(f"Suite error: {exc}", file=sys.stderr)
        return 2
    report = Evaluator(build_graph(args.node)).evaluate(cases)
    print(format_report(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
