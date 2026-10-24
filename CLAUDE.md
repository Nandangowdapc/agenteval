# AgentEval

Production evaluation framework for agentic AI systems, built on LangGraph. Python, personal/portfolio project.

## Stack
Python 3.11, LangGraph (StateGraph), LangChain + `langchain-groq` (Groq-hosted LLM inference, free tier), FastAPI/uvicorn/pydantic (API layer in `api/`), SQLAlchemy pinned in `requirements.txt` (unused), pytest, black, ruff.

## Core design decisions (don't relitigate without reason)
- **State is a plain `TypedDict`** (`AgentState` in `agent/state.py`), with `Annotated[list, add]` reducers for append-only fields (`messages`, `tool_calls`, `tool_results`, `errors`). No Pydantic model here — matches LangGraph's own idiom and keeps node functions returning plain dicts.
- **`AgentGraph` wraps `StateGraph`** rather than exposing it directly (`agent/graph.py`) — `add_node`/`add_edge`/`add_conditional_edges`/`run(task)`. `run()` compiles and invokes in one call; compilation is cheap enough at this scale that caching the compiled graph wasn't worth the complexity yet.
- **Tools are a simple registry** (`agent/tools.py`): a `Tool` wraps a plain callable + JSON-schema-shaped `parameters` for LLM function-calling; `ToolRegistry.get_schema()` hands that straight to an LLM. No LangChain `@tool` decorator used — kept framework-agnostic on purpose.
- **Providers are pluggable, Groq is the default** (`agent/providers.py`: `PROVIDERS` registry of groq/openai/anthropic/ollama, `create_chat_model`, `AGENTEVAL_PROVIDER`; non-Groq packages are optional extras imported lazily; `create_llm_node(model=None, tools=None, system_prompt=None, provider=None)`, `create_judge(provider, model, temperature)`, CLI `--provider/--model/--judge-provider/--judge-model`, `--node/--judge groq` kept as aliases of `llm`). Only Groq verified live; others mock-tested. Groq default model `openai/gpt-oss-120b` (llama-3.3-70b was retired by Groq; judge default is `qwen/qwen3.8-27b` to avoid self-preference). With a registry it binds tools via `bind_tools` (from `get_schema()`); assistant messages are plain dicts with optional `tool_calls` `[{id,name,args}]`, tool results are `{"role":"tool","tool_call_id","content"}` dicts, and the task is always prepended as a user message (not stored in `messages`). Reads `GROQ_API_KEY` from `.env` via `python-dotenv`; raises immediately with a setup hint if missing rather than failing deep in a LangGraph invoke.
- **Tool loop** (`agent/loop.py`, `build_tool_agent(llm_node, registry, max_steps=10)`): llm -> (tools -> llm)* -> END. Unknown tool / bad args are recorded in `errors` (so `success_rate` drops) but the error text is fed back to the LLM and the loop continues; tool-returned `"Error: ..."` strings (e.g. division by zero) are NOT agent errors. `current_step` counts LLM calls only. A `stop` node appends an error at `max_steps` LLM calls; `AgentGraph.recursion_limit` (default 25, set to `2*max_steps+5`) keeps our cap ahead of `GraphRecursionError`. `EvalCase.max_steps` only affects `step_efficiency`; the hard cap is the graph's `max_steps`.
- **`calculate` is an AST-walking evaluator, never `eval`**: numbers, unary +/-, `+ - * / // % **`; exponent capped at 100 plus a bit-length cap for chained powers.
- **Evaluation metrics are plain functions scored 0–1, higher is better** (`eval/metrics.py`): `exact_match`, `contains_match`, `tool_call_accuracy`, `step_efficiency`, `success_rate`, `latency_score`, `token_efficiency` (wired into `Evaluator` when `EvalCase.max_tokens` is set; `llm.py` records Groq `usage_metadata["total_tokens"]` per call into append-only `AgentState.token_usage`, nothing if missing). Kept as free functions (not a scorer class hierarchy) since each only needs a couple of primitive inputs — no shared state to justify a class yet.
- **`Evaluator` takes an already-wired `AgentGraph`**, not a factory — `AgentGraph.run()` already builds fresh initial state per call, so one graph instance can score many `EvalCase`s. Revisit this (e.g. add a factory variant) only if a node ever needs case-specific construction.
- **LLM-as-judge is opt-in and injectable** (`eval/judge.py`): a judge is any `str -> str` callable; `llm_judge(task, output, criteria, judge)` asks for a 0–10 rating, normalises to 0–1, and scores unparseable replies 0.0 (never raises). `Evaluator(graph, judge=None)` records `llm_judge` only when a judge AND `EvalCase.judge_criteria` are both set. `create_groq_judge()` is the real one (temperature 0). Lives outside `metrics.py` because it needs a callable, not primitives. The API injects it via the `get_judge_factory` dependency (overridden in tests; built only when a case has `judge_criteria`, else 503 without `GROQ_API_KEY`).
- **Tool-use system prompt**: `create_llm_node(..., system_prompt=None)` prepends `TOOL_SYSTEM_PROMPT` as a system message when tools are bound (fixed the model skipping `calculate`; `tool_call_accuracy` 0.33 -> 1.0 live).
- **Judge-bias mitigations**: rubric in the judge prompt; `llm_judge(samples=N)` takes the median; `Evaluator(judge_samples=N)`; CLI `--judge-samples N` (N>1 -> temperature 0.7, else 0.0). The API does not expose `judge_samples`.
- **API LLM node is injected** via the `get_llm_node_factory` FastAPI dependency (`api/app.py`); tests override it with a mock. `POST /evaluate` returns 503 without `GROQ_API_KEY`; `EvalCaseIn.judge_criteria` is accepted.
- **Suites are JSON/YAML** loaded by `load_suite` (`eval/suite.py`, raises `SuiteError`); CLI: `PYTHONPATH=src python -m agenteval.eval.suite <path> [--node mock|groq]`.
- **Eval tests run against a mock LLM node**, not the real Groq one, so `pytest` never needs a live API key. The real Groq node is exercised only through the examples, and only when `GROQ_API_KEY` is set.

## Package structure
```
src/agenteval/
  agent/
    state.py    AgentState TypedDict + create_initial_state
    graph.py    AgentGraph (StateGraph wrapper)
    tools.py    Tool, ToolRegistry, tool_registry (calculate, search)
    providers.py PROVIDERS registry, get_provider, create_chat_model
    llm.py      create_llm_node (provider-backed, Groq default, optional tool binding)
    loop.py     create_tool_node, create_router, build_tool_agent (tool-calling loop)
  eval/
    judge.py      llm_judge, parse_score, create_judge, create_groq_judge
    metrics.py    exact_match, contains_match, tool_call_accuracy, step_efficiency, success_rate, latency_score, token_efficiency
    evaluator.py  EvalCase, EvalResult, EvalReport, Evaluator (times runs)
    suite.py      load_suite (JSON/YAML), SuiteError, CLI (--node, --judge)
  api/
    app.py      FastAPI app: /health, /tools, /evaluate
    models.py   request/response pydantic models
tests/        pytest suite (test_agent.py, test_eval.py, test_loop.py, test_api.py, test_suite.py)
examples/     01_simple_agent.py (needs GROQ_API_KEY; also runs the tool loop), 02_evaluate_agent.py (mock node, no key needed), suite_arithmetic.json
```

## Roadmap / status
1. **Agent scaffold (complete, 2026-09-30)** — state/graph/tools/Groq LLM node, tests, example.
2. **Evaluation layer (complete, 2026-10-02)** — metrics + `Evaluator`/`EvalReport`, tests, example, README section.
3. **Multi-step tool-calling agent (complete, 2026-10-06)** — `agent/loop.py`, tool-binding in `llm.py`, safe `calculate`, `tests/test_loop.py` (47 tests total), example 01 extended. Run live 2026-10-22 (tool loop OK).
4. **API, suites/CLI, latency metric (complete, 2026-10-14)** — `api/` (6 tests, smoke-tested live with uvicorn 2026-10-17 (no key: /tools ok, /evaluate 503)), `eval/suite.py` + CLI + `examples/suite_arithmetic.json`, `latency_score`/`token_efficiency`, Evaluator timing. Token tracking added later the same day (`token_usage`, `max_tokens`, `tokens_used`). 83 tests total.
5. **LLM-as-judge (complete, 2026-10-17, uncommitted)** — `eval/judge.py`, `Evaluator(judge=)`, `EvalCase.judge_criteria`, suite field + `--judge groq` CLI flag, API `judge_criteria` + `get_judge_factory`, README. 92 tests total. Run live against Groq 2026-10-22 (agent `openai/gpt-oss-120b`, judge `qwen/qwen3.8-27b`): replies parsed, scores sensible.6. **Live Groq verification (complete, 2026-10-22, committed e256f6f)** — key in gitignored `.env`; llama-3.3-70b-versatile was retired (404), defaults now agent `openai/gpt-oss-120b`, judge `qwen/qwen3.8-27b`. Verified live: example 01 tool loop, suite CLI `--node groq --judge groq` (overall 0.66; model skipped `calculate` on 2+2), judge on 2 cases. 92 tests.
7. **Tool-use prompting, judge-bias mitigations, live `/evaluate` (complete, 2026-10-22)** — see Core decisions. `/evaluate` verified via uvicorn (12*12 case, overall 0.81, 532 tokens, `llm_judge` 1.0); 3-sample judge run OK. 95 tests total.
8. **Multi-provider LLM support (complete, 2026-10-24, uncommitted)** — `agent/providers.py` registry (groq default; openai, anthropic, ollama as optional extras), `create_llm_node(provider=)`, `create_judge()`, CLI `--provider/--model/--judge-provider/--judge-model`, README providers table. 107 tests. Groq re-verified live; other providers mock-tested only (default model IDs unverified). Decision: stay a library, no public website (shared-key quota/abuse, upkeep).
9. **Not started:**
   - Judge calibration set (judge scores vs human labels).
   - Expose `judge_samples` in the API.
   - Live-test a non-Groq provider and verify its default model IDs.

## Documentation duty
- `LEARN.md` is the long-form manual (problem, solution, method, rationale for every file/decision, from day one). After each user query that changes code, makes a decision, or answers a why/how question, run the `teacher` subagent (`.claude/agents/teacher.md`) with a summary of the query and outcome so it updates `LEARN.md`. `LEARN.md` is written in a story format (chapters, cast analogies) with all technical detail kept. `session-logger` still owns `PROJECT_LOG.md` and this file's roadmap.

## Gotchas
- Subagent files in `.claude/agents/` created mid-session aren't loadable by name until Claude Code restarts; run them via a general-purpose agent told to read the `.md` until then.
- The installed ruff enables a wider default rule set than E/F (I, UP, N, BLE, RUF...) with only `line-length` in `pyproject.toml`; numbered `examples/*` scripts have a per-file N999 ignore.
- Windows consoles default to a non-UTF-8 codepage; examples call `sys.stdout.reconfigure(encoding="utf-8")` before printing emoji — keep that pattern in new examples.
- Never put real keys in `.env.example` (tracked); use the gitignored `.env`. Groq retires models without notice (404) — check defaults in `agent/llm.py` and `eval/judge.py` first if live runs fail.
- `requirements.txt` versions were already present in the repo's `venv/` as of 2026-10-02 (`pip install -r requirements.txt` was a no-op) — if dependencies ever drift, check the venv before assuming a fresh install is needed.
