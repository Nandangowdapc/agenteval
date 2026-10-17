"""Pydantic request/response models for the HTTP API."""

from pydantic import BaseModel, Field


class EvalCaseIn(BaseModel):
    task: str = Field(min_length=1)
    expected_output: str | None = None
    expected_tools: list[str] = Field(default_factory=list)
    max_steps: int = Field(default=10, ge=1)
    max_tokens: int | None = Field(default=None, ge=1)
    judge_criteria: str | None = Field(default=None, min_length=1)


class EvaluateRequest(BaseModel):
    cases: list[EvalCaseIn] = Field(min_length=1)
    max_steps: int = Field(default=10, ge=1, le=50, description="Agent loop hard cap")


class CaseResultOut(BaseModel):
    task: str
    output: str
    scores: dict[str, float]
    overall: float
    steps: int
    tokens_used: int
    tool_calls: list[str]
    errors: list[str]


class EvaluateResponse(BaseModel):
    results: list[CaseResultOut]
    summary: dict[str, float]
    overall: float
    total_tokens: int = 0


class ToolOut(BaseModel):
    name: str
    description: str
    parameters: dict


class HealthResponse(BaseModel):
    status: str
