"""Tests for the FastAPI layer (mock LLM node, no API key required)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from src.agenteval.agent.tools import tool_registry
from src.agenteval.api.app import app, get_llm_node_factory


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
