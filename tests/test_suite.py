"""Tests for file-based suite loading and the suite CLI (mock node, no API key)."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agenteval.eval import EvalCase
from src.agenteval.eval.suite import SuiteError, load_suite, main

EXAMPLE = os.path.join(
    os.path.dirname(__file__), "..", "examples", "suite_arithmetic.json"
)


def write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content if isinstance(content, str) else json.dumps(content))
    return p


def test_load_json_object_and_list(tmp_path):
    case = {"task": "What is 1 + 1?", "expected_output": "2", "max_steps": 3}
    for data in ({"cases": [case]}, [case]):
        cases = load_suite(write(tmp_path, "s.json", data))
        assert cases == [
            EvalCase(task="What is 1 + 1?", expected_output="2", max_steps=3)
        ]


def test_defaults_applied(tmp_path):
    (c,) = load_suite(write(tmp_path, "s.json", [{"task": "hi"}]))
    assert c.expected_output is None and c.expected_tools == [] and c.max_steps == 10


def test_load_yaml(tmp_path):
    pytest.importorskip("yaml")
    text = "cases:\n  - task: What is 2 + 2?\n    expected_tools: [calculate]\n"
    assert load_suite(write(tmp_path, "s.yaml", text))[0].expected_tools == [
        "calculate"
    ]


@pytest.mark.parametrize(
    "data, message",
    [
        ([{"expected_output": "x"}], "case #1: 'task'"),
        ([{"task": "a"}, {"task": "b", "max_steps": 0}], "case #2: 'max_steps'"),
        ([{"task": "a", "max_steps": True}], "'max_steps'"),
        ([{"task": "a", "expected_tools": "calculate"}], "'expected_tools'"),
        ([{"task": "a", "bogus": 1}], "unknown field"),
        (["not an object"], "must be an object"),
        ([], "no cases"),
        ({"nope": []}, "'cases'"),
        (42, "expected a list"),
    ],
)
def test_validation_errors(tmp_path, data, message):
    with pytest.raises(SuiteError, match=message):
        load_suite(write(tmp_path, "s.json", data))


def test_file_errors(tmp_path):
    with pytest.raises(SuiteError, match="not found"):
        load_suite(tmp_path / "missing.json")
    with pytest.raises(SuiteError, match="invalid JSON"):
        load_suite(write(tmp_path, "bad.json", "{oops"))
    with pytest.raises(SuiteError, match="unsupported extension"):
        load_suite(write(tmp_path, "s.txt", "x"))


def test_cli_runs_example_suite_with_mock(capsys):
    assert main([EXAMPLE]) == 0
    out = capsys.readouterr().out
    assert "exact_match: 0.67" in out and "overall" in out


def test_cli_reports_bad_suite(tmp_path, capsys):
    assert main([str(write(tmp_path, "s.json", []))]) == 2
    assert "Suite error" in capsys.readouterr().err
