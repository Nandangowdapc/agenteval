"""Judge calibration tests: deterministic fake judges, no network."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agenteval.eval.calibration import (
    CalibrationError,
    calibrate,
    format_report,
    load_calibration,
    main,
)

EXAMPLE = os.path.join(
    os.path.dirname(__file__), "..", "examples", "judge_calibration.json"
)


def write(tmp_path, data):
    p = tmp_path / "c.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def item(score, **kw):
    return {"task": "t", "output": "o", "criteria": "c", "human_score": score, **kw}


def test_example_file_loads():
    items = load_calibration(EXAMPLE)
    assert len(items) >= 10
    assert all(0 <= i.human_score <= 1 for i in items)


def test_perfect_judge(tmp_path):
    items = load_calibration(write(tmp_path, [item(0), item(5), item(10)]))
    replies = iter(["0", "5", "10"])
    report = calibrate(items, lambda _: next(replies))
    assert report.mean_abs_error == 0
    assert report.bias == 0
    assert report.agreement == 1.0
    assert report.correlation == pytest.approx(1.0)


def test_lenient_judge_has_positive_bias(tmp_path):
    items = load_calibration(write(tmp_path, [item(0), item(4)]))
    report = calibrate(items, lambda _: "10")
    assert report.bias == pytest.approx(0.8)
    assert report.agreement == 0.0
    assert report.correlation is None  # judge scores are constant
    assert "n/a" in format_report(report)


def test_unparseable_reply_counts_as_zero(tmp_path):
    items = load_calibration(write(tmp_path, [item(0), item(10)]))
    report = calibrate(items, lambda _: "no idea")
    assert report.judge_scores == [0.0, 0.0]


@pytest.mark.parametrize(
    "data, match",
    [
        ("nope", "list of at least 2"),
        ([item(5)], "list of at least 2"),
        ([item(5), item(11)], "between 0 and 10"),
        ([item(5), item("x")], "'human_score'"),
        ([item(5), item(True)], "'human_score'"),
        ([item(5), item(5, task=" ")], "'task'"),
        ([item(5), 3], "must be an object"),
    ],
)
def test_bad_files_rejected(tmp_path, data, match):
    with pytest.raises(CalibrationError, match=match):
        load_calibration(write(tmp_path, data))


def test_missing_file():
    with pytest.raises(CalibrationError):
        load_calibration("does-not-exist.json")


def test_cli_bad_file_exit_code(tmp_path):
    assert main([str(tmp_path / "missing.json")]) == 2


def test_cli_without_key_raises(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        main([EXAMPLE])
