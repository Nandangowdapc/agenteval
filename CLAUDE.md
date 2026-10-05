# AgentEval

Production evaluation framework for agentic AI systems, built on LangGraph. Python, personal/portfolio project.

## Stack
Python 3.11, LangGraph (StateGraph), LangChain + `langchain-groq` (Groq-hosted LLM inference, free tier), FastAPI/uvicorn/pydantic/SQLAlchemy pinned in `requirements.txt` for a future API layer (not built yet), pytest, black, ruff.

## Core design decisions (don't relitigate without reason)
- **State is a plain `TypedDict`** (`AgentState` in `agent/state.py`), with `Annotated[list, add]` reducers for append-only fields (`messages`, `tool_calls`, `tool_results`, `errors`). No Pydantic model here — matches LangGraph's own idiom and keeps node functions returning plain dicts.
- **`AgentGraph` wraps `StateGraph`** rather than exposing it directly (`agent/graph.py`) — `add_node`/`add_edge`/`add_conditional_edges`/`run(task)`. `run()` compiles and invokes in one call; compilation is cheap enough at this scale that caching the compiled graph wasn't worth the complexity yet.
- **Tools are a simple registry** (`agent/tools.py`): a `Tool` wraps a plain callable + JSON-schema-shaped `parameters` for LLM function-calling; `ToolRegistry.get_schema()` hands that straight to an LLM. No LangChain `@tool` decorator used — kept framework-agnostic on purpose.
- **LLM node is Groq-only for now** (`agent/llm.py`, `create_llm_node`), default model `llama-3.3-70b-versatile`. Reads `GROQ_API_KEY` from `.env` via `python-dotenv`; raises immediately with a setup hint if missing rather than failing deep in a LangGraph invoke.
- **Evaluation metrics are plain functions scored 0–1, higher is better** (`eval/metrics.py`): `exact_match`, `contains_match`, `tool_call_accuracy`, `step_efficiency`, `success_rate`. Kept as free functions (not a scorer class hierarchy) since each only needs a couple of primitive inputs — no shared state to justify a class yet.
- **`Evaluator` takes an already-wired `AgentGraph`**, not a factory — `AgentGraph.run()` already builds fresh initial state per call, so one graph instance can score many `EvalCase`s. Revisit this (e.g. add a factory variant) only if a node ever needs case-specific construction.
- **Eval tests run against a mock LLM node**, not the real Groq one, so `pytest` never needs a live API key. The real Groq node is exercised only through the examples, and only when `GROQ_API_KEY` is set.

## Package structure
```
src/agenteval/
  agent/
    state.py    AgentState TypedDict + create_initial_state
    graph.py    AgentGraph (StateGraph wrapper)
    tools.py    Tool, ToolRegistry, tool_registry (calculate, search)
    llm.py      create_llm_node (Groq-backed)
  eval/
    metrics.py    exact_match, contains_match, tool_call_accuracy, step_efficiency, success_rate
    evaluator.py  EvalCase, EvalResult, EvalReport, Evaluator
tests/        pytest suite (test_agent.py, test_eval.py)
examples/     01_simple_agent.py (needs GROQ_API_KEY), 02_evaluate_agent.py (mock node, no key needed)
```

## Roadmap / status
1. **Agent scaffold (complete, 2026-09-30)** — state/graph/tools/Groq LLM node, tests, example.
2. **Evaluation layer (complete, 2026-10-02)** — metrics + `Evaluator`/`EvalReport`, tests, example, README section.
3. **Not started:**
   - `GROQ_API_KEY` setup — deliberately postponed; `examples/01_simple_agent.py` and any real (non-mock) evaluation run are blocked on this.
   - FastAPI layer — dependency is pinned but no routes exist yet.
   - Multi-step/looping agent (conditional edges, tool-calling loop) — current example is a single LLM node straight to `END`.
   - More realistic metrics (e.g. LLM-as-judge scoring, latency/cost tracking) — current metrics are all deterministic/local.
   - A CLI or file-based (JSON/YAML) way to define `EvalCase` suites instead of constructing them in Python.

## Gotchas
- Windows consoles default to a non-UTF-8 codepage; examples call `sys.stdout.reconfigure(encoding="utf-8")` before printing emoji — keep that pattern in new examples.
- `requirements.txt` versions were already present in the repo's `venv/` as of 2026-10-02 (`pip install -r requirements.txt` was a no-op) — if dependencies ever drift, check the venv before assuming a fresh install is needed.
