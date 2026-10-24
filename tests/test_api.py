"""Tests for the FastAPI layer (mock LLM node, no API key required)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from src.agenteval.agent.tools import tool_registry
from src.agenteval.api.app import app, get_judge_factory, get_llm_node_factory


def scripted_factory(script):
    def factory(registry):
        def node(state):
            content, calls = script[min(state["current_step"], len(script) - 1)]
            message = {"role": "assistant", "content": content}
            if calls:
                message["tool_calls"] = calls
            return {
                "messages": [message],
                "tool_calls": calls,
                "token_usage": [10],
                "current_step": state["current_step"] + 1,
            }

        return node

    return factory


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def use_script(script):
    app.dependency_overrides[get_llm_node_factory] = lambda: scripted_factory(script)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_tools_lists_registry(client):
    r = client.get("/tools")
    assert r.status_code == 200
    names = {t["name"] for t in r.json()}
    assert names == set(tool_registry.list_tools())
    assert "calculate" in names


def test_evaluate_with_tool_call(client):
    call = {"id": "c1", "name": "calculate", "args": {"expression": "2 + 2"}}
    use_script([("", [call]), ("4", [])])
    r = client.post(
        "/evaluate",
        json={
            "cases": [
                {
                    "task": "What is 2 + 2?",
                    "expected_output": "4",
                    "expected_tools": ["calculate"],
                }
            ]
        },
    )
    assert r.status_code == 200
    body = r.json()
    result = body["results"][0]
    assert result["output"] == "4"
    assert result["steps"] == 2
    assert result["tool_calls"] == ["calculate"]
    assert result["errors"] == []
    assert result["scores"]["exact_match"] == 1.0
    assert result["scores"]["tool_call_accuracy"] == 1.0
    assert body["summary"]["overall"] == body["overall"]


def test_evaluate_multiple_cases(client):
    use_script([("hi", [])])
    r = client.post("/evaluate", json={"cases": [{"task": "a"}, {"task": "b"}]})
    assert r.status_code == 200
    assert len(r.json()["results"]) == 2


def test_evaluate_validation_errors(client):
    assert client.post("/evaluate", json={"cases": []}).status_code == 422
    assert client.post("/evaluate", json={}).status_code == 422


def test_evaluate_without_key_returns_503(client, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    r = client.post("/evaluate", json={"cases": [{"task": "x"}]})
    assert r.status_code == 503


def test_evaluate_tokens(client):
    call = {"id": "c1", "name": "calculate", "args": {"expression": "2 + 2"}}
    use_script([("", [call]), ("4", [])])
    r = client.post(
        "/evaluate",
        json={"cases": [{"task": "What is 2 + 2?", "max_tokens": 40}]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["results"][0]["tokens_used"] == 20
    assert body["results"][0]["scores"]["token_efficiency"] == 0.5
    assert body["total_tokens"] == 20


def test_evaluate_without_max_tokens(client):
    use_script([("hi", [])])
    body = client.post("/evaluate", json={"cases": [{"task": "a"}]}).json()
    assert "token_efficiency" not in body["results"][0]["scores"]
    assert body["results"][0]["tokens_used"] == 10


def test_evaluate_rejects_bad_max_tokens(client):
    r = client.post("/evaluate", json={"cases": [{"task": "a", "max_tokens": 0}]})
    assert r.status_code == 422


def test_evaluate_with_judge(client):
    use_script([("4", [])])
    app.dependency_overrides[get_judge_factory] = lambda: lambda _t: (lambda _: "8")
    r = client.post(
        "/evaluate",
        json={"cases": [{"task": "2+2?", "judge_criteria": "answer is 4"}]},
    )
    assert r.status_code == 200
    assert r.json()["results"][0]["scores"]["llm_judge"] == 0.8


def test_judge_not_built_without_criteria(client):
    use_script([("4", [])])

    def boom():
        raise AssertionError("judge factory should not be called")

    app.dependency_overrides[get_judge_factory] = lambda: boom
    r = client.post("/evaluate", json={"cases": [{"task": "2+2?"}]})
    assert r.status_code == 200
    assert "llm_judge" not in r.json()["results"][0]["scores"]


def test_judge_samples_takes_median_and_raises_temperature(client):
    use_script([("4", [])])
    replies = iter(["2", "9", "8"])
    temps = []

    def factory(temperature):
        temps.append(temperature)
        return lambda _: next(replies)

    app.dependency_overrides[get_judge_factory] = lambda: factory
    r = client.post(
        "/evaluate",
        json={
            "cases": [{"task": "2+2?", "judge_criteria": "answer is 4"}],
            "judge_samples": 3,
        },
    )
    assert r.status_code == 200
    assert r.json()["results"][0]["scores"]["llm_judge"] == 0.8
    assert temps == [0.7]


def test_judge_samples_default_is_deterministic(client):
    use_script([("4", [])])
    temps = []

    def factory(temperature):
        temps.append(temperature)
        return lambda _: "8"

    app.dependency_overrides[get_judge_factory] = lambda: factory
    client.post(
        "/evaluate",
        json={"cases": [{"task": "x", "judge_criteria": "ok"}]},
    )
    assert temps == [0.0]


def test_judge_samples_out_of_range_rejected(client):
    r = client.post("/evaluate", json={"cases": [{"task": "a"}], "judge_samples": 6})
    assert r.status_code == 422


def test_judge_criteria_without_key_returns_503(client, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    use_script([("4", [])])
    r = client.post(
        "/evaluate", json={"cases": [{"task": "x", "judge_criteria": "ok"}]}
    )
    assert r.status_code == 503
