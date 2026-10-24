"""LLM provider registry: which hosted model service backs the agent and the judge.

Groq is the default. Each provider lazily imports its own LangChain package, so
only the one you use needs installing (`pip install agenteval[openai]` etc.).
All of them expose the same `.invoke()` / `.bind_tools()` / `usage_metadata`
interface, so `llm.py` and `judge.py` don't care which one they got.
"""

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

load_dotenv()

DEFAULT_PROVIDER = "groq"
PROVIDER_ENV_VAR = "AGENTEVAL_PROVIDER"


@dataclass(frozen=True)
class Provider:
    name: str
    env_var: str | None  # API-key variable; None for providers that need no key
    default_model: str  # agent model
    default_judge_model: str  # judge model, deliberately not the agent's
    signup_hint: str
    extra: str  # pip extra that installs the LangChain package
    factory: Callable[..., Any]  # (model, api_key, temperature) -> chat model


def _groq(model: str, api_key: str | None, temperature: float | None):
    from langchain_groq import ChatGroq

    return ChatGroq(model=model, api_key=api_key, **_temp(temperature))


def _openai(model: str, api_key: str | None, temperature: float | None):
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=model, api_key=api_key, **_temp(temperature))


def _anthropic(model: str, api_key: str | None, temperature: float | None):
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model=model, api_key=api_key, **_temp(temperature))


def _ollama(model: str, api_key: str | None, temperature: float | None):
    from langchain_ollama import ChatOllama

    return ChatOllama(model=model, **_temp(temperature))


def _temp(temperature: float | None) -> dict:
    return {} if temperature is None else {"temperature": temperature}


# Hosted model names go stale (Groq already retired one): keep them all here.
PROVIDERS: dict[str, Provider] = {
    p.name: p
    for p in (
        Provider(
            "groq",
            "GROQ_API_KEY",
            "openai/gpt-oss-120b",
            "qwen/qwen3.8-27b",
            "https://console.groq.com/keys",
            "groq",
            _groq,
        ),
        Provider(
            "openai",
            "OPENAI_API_KEY",
            "gpt-4o-mini",
            "gpt-4o",
            "https://platform.openai.com/api-keys",
            "openai",
            _openai,
        ),
        Provider(
            "anthropic",
            "ANTHROPIC_API_KEY",
            "claude-haiku-5-5",
            "claude-sonnet-5-5",
            "https://console.anthropic.com/settings/keys",
            "anthropic",
            _anthropic,
        ),
        Provider(
            "ollama",
            None,
            "llama3.1",
            "qwen2.5",
            "https://ollama.com/download (run `ollama pull <model>` first)",
            "ollama",
            _ollama,
        ),
    )
}


def get_provider(name: str | None = None) -> Provider:
    """Resolve a provider: explicit name, else $AGENTEVAL_PROVIDER, else Groq."""
    name = (name or os.environ.get(PROVIDER_ENV_VAR) or DEFAULT_PROVIDER).lower()
    try:
        return PROVIDERS[name]
    except KeyError:
        raise ValueError(
            f"Unknown provider {name!r}; choose one of {sorted(PROVIDERS)}"
        ) from None


def create_chat_model(
    provider: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    judge: bool = False,
):
    """Build a LangChain chat model for `provider` (default model per provider).

    Raises immediately with a setup hint if the key or package is missing,
    rather than failing deep inside a LangGraph invoke. `judge=True` picks the
    provider's judge default model instead of its agent default.
    """
    spec = get_provider(provider)
    api_key = None
    if spec.env_var:
        api_key = os.environ.get(spec.env_var)
        if not api_key:
            raise RuntimeError(
                f"{spec.env_var} is not set. Copy .env.example to .env and add "
                f"your key from {spec.signup_hint}"
            )
    model = model or (spec.default_judge_model if judge else spec.default_model)
    try:
        return spec.factory(model, api_key, temperature)
    except ImportError as exc:
        raise ImportError(
            f"Provider {spec.name!r} needs an extra package: "
            f"pip install 'agenteval[{spec.extra}]'"
        ) from exc
