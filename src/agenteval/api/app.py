"""FastAPI app: health, tool listing, and eval runs.

The LLM node comes from the `get_llm_node_factory` dependency so tests can
override it with a mock via `app.dependency_overrides`; the default factory
builds the real Groq node and only works when GROQ_API_KEY is set.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException

from ..agent.loop import build_tool_agent
from ..agent.state import AgentState
from ..agent.tools import ToolRegistry, tool_registry
from ..eval.evaluator import EvalCase, Evaluator
from ..eval.judge import Judge
from .models import (
    CaseResultOut,
    EvaluateRequest,
    EvaluateResponse,
    HealthResponse,
    ToolOut,
)

LLMNode = Callable[[AgentState], dict]
LLMNodeFactory = Callable[[ToolRegistry], LLMNode]
JudgeFactory = Callable[[], Judge]

app = FastAPI(title="AgentEval API", version="0.1.0")


def groq_llm_node_factory(registry: ToolRegistry) -> LLMNode:
    """Default factory: the configured provider's node (Groq unless
    $AGENTEVAL_PROVIDER says otherwise); 503 if its key is missing."""
    from ..agent.llm import create_llm_node

    try:
        return create_llm_node(tools=registry)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def get_llm_node_factory() -> LLMNodeFactory:
    """Dependency returning the LLM node factory (override in tests)."""
    return groq_llm_node_factory


def groq_judge_factory() -> Judge:
    """Default judge factory: the configured provider's judge; 503 if no key."""
    from ..eval.judge import create_judge

    try:
        return create_judge()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def get_judge_factory() -> JudgeFactory:
    """Dependency returning the judge factory (override in tests)."""
    return groq_judge_factory


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/tools", response_model=list[ToolOut])
def list_tools() -> list[ToolOut]:
    return [
        ToolOut(name=name, **schema)
        for name, schema in tool_registry.get_schema().items()
    ]


@app.post("/evaluate", response_model=EvaluateResponse)
def evaluate(
    request: EvaluateRequest,
    factory: Annotated[LLMNodeFactory, Depends(get_llm_node_factory)],
    judge_factory: Annotated[JudgeFactory, Depends(get_judge_factory)],
) -> EvaluateResponse:
    graph = build_tool_agent(
        factory(tool_registry), tool_registry, max_steps=request.max_steps
    )
    # Only build a judge when some case asks for one, so plain runs never need it.
    judge = judge_factory() if any(c.judge_criteria for c in request.cases) else None
    report = Evaluator(graph, judge=judge).evaluate(
        [EvalCase(**case.model_dump()) for case in request.cases]
    )
    results = []
    for r in report.results:
        state = r.final_state
        messages = state["messages"]
        results.append(
            CaseResultOut(
                task=r.case.task,
                output=str(messages[-1]["content"]) if messages else "",
                scores=r.scores,
                overall=r.overall,
                steps=state["current_step"],
                tokens_used=r.tokens_used,
                tool_calls=[tc["name"] for tc in state["tool_calls"]],
                errors=list(state["errors"]),
            )
        )
    return EvaluateResponse(
        results=results,
        summary=report.summary(),
        overall=report.overall,
        total_tokens=report.total_tokens,
    )
