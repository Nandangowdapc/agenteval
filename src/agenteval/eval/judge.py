"""LLM-as-judge scoring: ask a model to grade an agent's answer against criteria.

A judge is any callable `str -> str` (prompt in, reply out), so tests can inject
a deterministic one and `create_groq_judge` supplies the real thing.
"""

import os
import re
from collections.abc import Callable

from dotenv import load_dotenv

load_dotenv()

Judge = Callable[[str], str]

DEFAULT_JUDGE_MODEL = "qwen/qwen3.8-27b"

_PROMPT = """You are grading an AI agent's answer.

Task given to the agent:
{task}

Agent's answer:
{output}

Grading criteria:
{criteria}

Rate how well the answer meets the criteria on a scale from 0 to 10
(0 = completely fails, 10 = fully meets). Reply with only the number."""

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def parse_score(reply: str, scale: float = 10.0) -> float | None:
    """Pull the first number out of a judge reply and normalise it to [0, 1].

    Returns None if the reply has no number. Values above `scale` are clamped.
    """
    match = _NUMBER.search(reply)
    if match is None:
        return None
    return min(1.0, max(0.0, float(match.group()) / scale))


def llm_judge(task: str, output: str, criteria: str, judge: Judge) -> float:
    """Score `output` against `criteria` in [0, 1] using `judge`.

    An unparseable reply scores 0.0 rather than raising, so one flaky judge
    response doesn't abort a whole evaluation run.
    """
    reply = judge(_PROMPT.format(task=task, output=output, criteria=criteria))
    score = parse_score(reply)
    return 0.0 if score is None else score


def create_groq_judge(model: str = DEFAULT_JUDGE_MODEL) -> Judge:
    """Build a judge backed by Groq (needs GROQ_API_KEY), temperature 0."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Copy .env.example to .env and add your key "
            "from https://console.groq.com/keys"
        )
    from langchain_groq import ChatGroq

    llm = ChatGroq(model=model, api_key=api_key, temperature=0)

    def judge(prompt: str) -> str:
        return str(llm.invoke(prompt).content)

    return judge
