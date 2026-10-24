"""Provider registry tests: no network, no keys, no optional packages needed."""

import pytest

from src.agenteval.agent import providers
from src.agenteval.agent.providers import (
    DEFAULT_PROVIDER,
    PROVIDERS,
    create_chat_model,
    get_provider,
)
from src.agenteval.eval.judge import create_judge
from src.agenteval.eval.suite import main

EXAMPLE = "examples/suite_arithmetic.json"


def test_registry_and_default():
    assert set(PROVIDERS) == {"groq", "openai", "anthropic", "ollama"}
    assert DEFAULT_PROVIDER == "groq"


def test_get_provider_resolution(monkeypatch):
    monkeypatch.delenv("AGENTEVAL_PROVIDER", raising=False)
    assert get_provider().name == "groq"
    monkeypatch.setenv("AGENTEVAL_PROVIDER", "OpenAI")
    assert get_provider().name == "openai"
    assert get_provider("anthropic").name == "anthropic"  # explicit beats env


def test_unknown_provider():
    with pytest.raises(ValueError, match="Unknown provider 'nope'"):
        get_provider("nope")


@pytest.mark.parametrize("name", ["groq", "openai", "anthropic"])
def test_missing_key_hint(monkeypatch, name):
    env_var = PROVIDERS[name].env_var
    monkeypatch.delenv(env_var, raising=False)
    with pytest.raises(RuntimeError, match=env_var):
        create_chat_model(name)


def test_ollama_needs_no_key(monkeypatch):
    seen = {}

    def fake(model, api_key, temperature):
        seen.update(model=model, api_key=api_key, temperature=temperature)
        return "chat"

    monkeypatch.setitem(PROVIDERS, "ollama", _with_factory("ollama", fake))
    assert create_chat_model("ollama") == "chat"
    assert seen == {"model": "llama3.1", "api_key": None, "temperature": None}


def test_default_and_judge_models(monkeypatch):
    seen = []
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setitem(
        PROVIDERS, "openai", _with_factory("openai", lambda m, k, t: seen.append(m))
    )
    create_chat_model("openai")
    create_chat_model("openai", judge=True)
    create_chat_model("openai", "custom")
    spec = PROVIDERS["openai"]
    assert seen == [spec.default_model, spec.default_judge_model, "custom"]


def test_missing_extra_hint(monkeypatch):
    def boom(model, api_key, temperature):
        raise ImportError("no module")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setitem(PROVIDERS, "anthropic", _with_factory("anthropic", boom))
    with pytest.raises(ImportError, match=r"agenteval\[anthropic\]"):
        create_chat_model("anthropic")


def test_create_judge_uses_provider_and_temperature(monkeypatch):
    class Reply:
        content = "7"

    class Chat:
        def invoke(self, prompt):
            return Reply()

    seen = {}

    def fake(model, api_key, temperature):
        seen.update(model=model, temperature=temperature)
        return Chat()

    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setitem(PROVIDERS, "openai", _with_factory("openai", fake))
    judge = create_judge("openai", temperature=0.7)
    assert judge("rate this") == "7"
    assert seen == {
        "model": PROVIDERS["openai"].default_judge_model,
        "temperature": 0.7,
    }


def test_cli_provider_missing_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        main([EXAMPLE, "--node", "llm", "--provider", "openai"])


def test_cli_judge_provider_missing_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        main([EXAMPLE, "--judge", "llm", "--judge-provider", "anthropic"])


def _with_factory(name, factory):
    from dataclasses import replace

    return replace(providers.PROVIDERS[name], factory=factory)
