# AgentEval

Production evaluation framework for agentic AI systems, built on LangGraph. Python, personal/portfolio project.

## Stack
Python 3.11, LangGraph (StateGraph), LangChain + `langchain-groq` (Groq-hosted LLM inference, free tier), FastAPI/uvicorn/pydantic (API layer in `api/`), SQLAlchemy pinned in `requirements.txt` (unused), pytest, black, ruff.

## Core design decisions (don't relitigate without reason)
- **State is a plain `TypedDict`** (`AgentState` in `agent/state.py`), with `Annotated[list, add]` reducers for append-only fields (`messages`, `tool_calls`, `tool_results`, `errors`). No Pydantic model here — matches LangGraph's own idiom and keeps node functions returning plain dicts.
- **`AgentGraph` wraps `StateGraph`** rather than exposing it directly (`agent/graph.py`) — `add_node`/`add_edge`/`add_conditional_edges`/`run(task)`. `run()` compiles and invokes in one call; compilation is cheap enough at this scale that caching the compiled graph wasn't worth the complexity yet.
- **Tools are a simple registry** (`agent/tools.py`): a `Tool` wraps a plain callable + JSON-schema-shaped `parameters` for LLM function-calling; `ToolRegistry.get_schema()` hands that straight to an LLM. No LangChain `@tool` decorator used — kept framework-agnostic on purpose.
- **LLM node is Groq-only for now** (`agent/llm.py`, `create_llm_node(model, tools=None)`), default model `llama-3.3-70b-versatile`. With a registry it binds tools via `bind_tools` (from `get_schema()`); assistant messages are plain dicts with optional `tool_calls` `[{id,name,args}]`, tool results are `{"role":"tool","tool_call_id","content"}` dicts, and the task is always prepended as a user message (not stored in `messages`). Reads `GROQ_API_KEY` from `.env` via `python-dotenv`; raises immediately with a setup hint if missing rather than failing deep in a LangGraph invoke.
- **Tool loop** (`agent/loop.py`, `build_tool_agent(llm_node, registry, max_steps=10)`): llm -> (tools -> llm)* -> END. Unknown tool / bad args are recorded in `errors` (so `success_rate` drops) but the error text is fed back to the LLM and the loop continues; tool-returned `"Error: ..."` strings (e.g. division by zero) are NOT agent errors. `current_step` counts LLM calls only. A `stop` node appends an error at `max_steps` LLM calls; `AgentGraph.recursion_limit` (default 25, set to `2*max_steps+5`) keeps our cap ahead of `GraphRecursionError`. `EvalCase.max_steps` only affects `step_efficiency`; the hard cap is the graph's `max_steps`.
- **`calculate` is an AST-walking evaluator, never `eval`**: numbers, unary +/-, `+ - * / // % **`; exponent capped at 100 plus a bit-length cap for chained powers.
- **Evaluation metrics are plain functions scored 0–1, higher is better** (`eval/metrics.py`): `exact_match`, `contains_match`, `tool_call_accuracy`, `step_efficiency`, `success_rate`, `latency_score`, `token_efficiency` (the last is not wired into `Evaluator`; needs Groq `usage_metadata` captured in state). Kept as free functions (not a scorer class hierarchy) since each only needs a couple of primitive inputs — no shared state to justify a class yet.
- **`Evaluator` takes an already-wired `AgentGraph`**, not a factory — `AgentGraph.run()` already builds fresh initial state per call, so one graph instance can score many `EvalCase`s. Revisit this (e.g. add a factory variant) only if a node ever needs case-specific construction.
- **API LLM node is injected** via the `get_llm_node_factory` FastAPI dependency (`api/app.py`); tests override it with a mock. `POST /evaluate` returns 503 without `GROQ_API_KEY`.
- **Suites are JSON/YAML** loaded by `load_suite` (`eval/suite.py`, raises `SuiteError`); CLI: `PYTHONPATH=src python -m agenteval.eval.suite <path> [--node mock|groq]`.
- **Eval tests run against a mock LLM node**, not the real Groq one, so `pytest` never needs a live API key. The real Groq node is exercised only through the examples, and only when `GROQ_API_KEY` is set.

## Package structure
```
src/agenteval/
  agent/
    state.py    AgentState TypedDict + create_initial_state
    graph.py    AgentGraph (StateGraph wrapper)
    tools.py    Tool, ToolRegistry, tool_registry (calculate, search)
    llm.py      create_llm_node (Groq-backed, optional tool binding)
    loop.py     create_tool_node, create_router, build_tool_agent (tool-calling loop)
  eval/
    metrics.py    exact_match, contains_match, tool_call_accuracy, step_efficiency, success_rate, latency_score, token_efficiency
    evaluator.py  EvalCase, EvalResult, EvalReport, Evaluator (times runs)
    suite.py      load_suite (JSON/YAML), SuiteError, CLI
  api/
    app.py      FastAPI app: /health, /tools, /evaluate
    models.py   request/response pydantic models
tests/        pytest suite (test_agent.py, test_eval.py, test_loop.py, test_api.py, test_suite.py)
examples/     01_simple_agent.py (needs GROQ_API_KEY; also runs the tool loop), 02_evaluate_agent.py (mock node, no key needed), suite_arithmetic.json
```

## Roadmap / status
1. **Agent scaffold (complete, 2026-09-30)** — state/graph/tools/Groq LLM node, tests, example.
2. **Evaluation layer (complete, 2026-10-02)** — metrics + `Evaluator`/`EvalReport`, tests, example, README section.
3. **Multi-step tool-calling agent (complete, 2026-10-06)** — `agent/loop.py`, tool-binding in `llm.py`, safe `calculate`, `tests/test_loop.py` (47 tests total), example 01 extended. Never run live (no key).
4. **API, suites/CLI, latency metric (complete, 2026-10-14, uncommitted)** — `api/` (6 tests, never run live with uvicorn), `eval/suite.py` + CLI + `examples/suite_arithmetic.json`, `latency_score`/`token_efficiency`, Evaluator timing. 72 tests total.
5. **Not started:**
   - `GROQ_API_KEY` setup — deliberately postponed; `examples/01_simple_agent.py`, the suite CLI with `--node groq`, `/evaluate` live, and any real evaluation run are blocked on this. Untested risk: Groq/llama may emit malformed tool calls, making `langchain_groq` raise.
   - Wire `token_efficiency` into `Evaluator` (capture Groq `usage_metadata` in `AgentState`/`llm.py`); no dollar-cost metric.
   - LLM-as-judge scoring.

## Gotchas
- Subagent files in `.claude/agents/` created mid-session aren't loadable by name until Claude Code restarts; run them via a general-purpose agent told to read the `.md` until then.
- The installed ruff enables a wider default rule set than E/F (I, UP, N, BLE, RUF...) with only `line-length` in `pyproject.toml`; numbered `examples/*` scripts have a per-file N999 ignore.
- Windows consoles default to a non-UTF-8 codepage; examples call `sys.stdout.reconfigure(encoding="utf-8")` before printing emoji — keep that pattern in new examples.
- `requirements.txt` versions were already present in the repo's `venv/` as of 2026-10-02 (`pip install -r requirements.txt` was a no-op) — if dependencies ever drift, check the venv before assuming a fresh install is needed.
