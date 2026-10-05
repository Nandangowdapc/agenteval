"""Scoring metrics for agent runs.

Every metric returns a float in [0, 1] where higher is better.
"""


def exact_match(output: str, expected: str) -> float:
    """1.0 if output equals expected (whitespace-insensitive)."""
    return 1.0 if output.strip() == expected.strip() else 0.0


def contains_match(output: str, expected: str) -> float:
    """1.0 if expected appears anywhere in output (case-insensitive)."""
    return 1.0 if expected.lower() in output.lower() else 0.0


def tool_call_accuracy(called_tools: list[str], expected_tools: list[str]) -> float:
    """Fraction of expected tools that were actually called."""
    if not expected_tools:
        return 1.0
    called = set(called_tools)
    expected = set(expected_tools)
    return len(called & expected) / len(expected)


def step_efficiency(steps_taken: int, max_steps: int) -> float:
    """1.0 for a single step, decaying linearly to 0.0 at max_steps."""
    if max_steps <= 1:
        return 1.0 if steps_taken <= 1 else 0.0
    return max(0.0, 1.0 - (steps_taken - 1) / (max_steps - 1))


def success_rate(errors: list[str]) -> float:
    """1.0 if the run produced no errors, else 0.0."""
    return 0.0 if errors else 1.0
