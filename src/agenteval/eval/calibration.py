"""Judge calibration: compare an LLM judge's scores with human labels.

A calibration file is a JSON list of `{task, output, criteria, human_score}`
items, `human_score` on the same 0-10 scale the judge uses. `calibrate` runs the
judge on each item and reports how closely it tracks the humans. CLI:

    python -m agenteval.eval.calibration examples/judge_calibration.json
        [--judge-provider groq] [--judge-model M] [--judge-samples N]
"""

import argparse
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

from ..agent.providers import PROVIDERS
from .judge import Judge, llm_judge

AGREEMENT_TOLERANCE = 0.2  # judge within 2 points of the human counts as agreeing


class CalibrationError(ValueError):
    """The calibration file is missing, malformed, or has a bad item."""


@dataclass
class CalibrationItem:
    task: str
    output: str
    criteria: str
    human_score: float  # normalised to [0, 1]


@dataclass
class CalibrationReport:
    items: list[CalibrationItem]
    judge_scores: list[float]

    @property
    def mean_abs_error(self) -> float:
        return statistics.fmean(
            abs(j - i.human_score) for i, j in zip(self.items, self.judge_scores)
        )

    @property
    def agreement(self) -> float:
        """Share of items where the judge is within the tolerance of the human."""
        close = sum(
            abs(j - i.human_score) <= AGREEMENT_TOLERANCE + 1e-9
            for i, j in zip(self.items, self.judge_scores)
        )
        return close / len(self.items)

    @property
    def correlation(self) -> float | None:
        """Pearson r between judge and human scores; None if either is constant."""
        humans = [i.human_score for i in self.items]
        try:
            return statistics.correlation(humans, self.judge_scores)
        except statistics.StatisticsError:
            return None

    @property
    def bias(self) -> float:
        """Mean (judge - human): positive means the judge is more lenient."""
        return statistics.fmean(
            j - i.human_score for i, j in zip(self.items, self.judge_scores)
        )


def load_calibration(path: str | Path) -> list[CalibrationItem]:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CalibrationError(f"{path}: {exc}") from exc
    if not isinstance(data, list) or len(data) < 2:
        raise CalibrationError(f"{path}: need a list of at least 2 items")
    items = []
    for n, raw in enumerate(data, 1):
        where = f"{path}: item #{n}"
        if not isinstance(raw, dict):
            raise CalibrationError(f"{where} must be an object")
        for key in ("task", "output", "criteria"):
            if not isinstance(raw.get(key), str) or not raw[key].strip():
                raise CalibrationError(f"{where}: '{key}' must be a non-empty string")
        score = raw.get("human_score")
        if isinstance(score, bool) or not isinstance(score, int | float):
            raise CalibrationError(f"{where}: 'human_score' must be a number 0-10")
        if not 0 <= score <= 10:
            raise CalibrationError(f"{where}: 'human_score' must be between 0 and 10")
        items.append(
            CalibrationItem(raw["task"], raw["output"], raw["criteria"], score / 10)
        )
    return items


def calibrate(
    items: list[CalibrationItem], judge: Judge, samples: int = 1
) -> CalibrationReport:
    scores = [llm_judge(i.task, i.output, i.criteria, judge, samples) for i in items]
    return CalibrationReport(items, scores)


def format_report(report: CalibrationReport) -> str:
    lines = [
        f"human {i.human_score:.2f}  judge {j:.2f}  {i.task!r}"
        for i, j in zip(report.items, report.judge_scores)
    ]
    r = report.correlation
    lines += [
        f"Items: {len(report.items)}",
        f"Mean absolute error: {report.mean_abs_error:.3f}",
        f"Bias (judge - human): {report.bias:+.3f}",
        f"Agreement within {AGREEMENT_TOLERANCE}: {report.agreement:.0%}",
        "Correlation: " + ("n/a (constant scores)" if r is None else f"{r:.3f}"),
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calibrate an LLM judge.")
    parser.add_argument("path", help="calibration file (.json)")
    parser.add_argument("--judge-provider", choices=sorted(PROVIDERS))
    parser.add_argument("--judge-model")
    parser.add_argument("--judge-samples", type=int, default=1)
    args = parser.parse_args(argv)

    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        items = load_calibration(args.path)
    except CalibrationError as exc:
        print(f"Calibration error: {exc}", file=sys.stderr)
        return 2
    from .judge import create_judge

    judge = create_judge(
        args.judge_provider,
        args.judge_model,
        temperature=0.7 if args.judge_samples > 1 else 0.0,
    )
    print(format_report(calibrate(items, judge, args.judge_samples)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
