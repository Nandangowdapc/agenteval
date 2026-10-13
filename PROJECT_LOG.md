# Project Log

Running log for continuity across sessions. Newest entries at the top. See `CLAUDE.md` for the standing architecture summary.

---

## 2026-10-14 (later) — token_efficiency wired into Evaluator

Added append-only `AgentState.token_usage` (ints, total tokens per LLM call); `llm.py` records `response.usage_metadata["total_tokens"]` (nothing if missing/None). `EvalCase.max_tokens: int | None = None` adds a `token_efficiency` score from `sum(token_usage)`; `EvalResult.tokens_used`, `EvalReport.total_tokens` / `mean_tokens`. `max_tokens` accepted in suite files (positive int, bool rejected) and the API (`EvalCaseIn.max_tokens`; results include `tokens_used`, response `total_tokens`). Unset `max_tokens` leaves behavior unchanged. Mock nodes in tests return `token_usage`; the Groq node is tested with a fake `ChatGroq`. **83 tests pass**, black/ruff clean. Uncommitted. Still no dollar-cost metric; never run with a real Groq key.

---

## 2026-10-14 — FastAPI layer, file-based suites + CLI, latency/token metrics

**FastAPI layer:** `src/agenteval/api/` (`app.py`, `models.py`) with `GET /health`, `GET /tools`, `POST /evaluate`. The LLM node comes from an injectable dependency `get_llm_node_factory`, so tests override it with a mock; without `GROQ_API_KEY` `/evaluate` returns 503. `tests/test_api.py` (6 tests). Never run live under uvicorn.

**File-based suites + CLI:** `src/agenteval/eval/suite.py` — `load_suite` (JSON/YAML), `SuiteError`, and a CLI `python -m agenteval.eval.suite <path> [--node mock|groq]` (needs `PYTHONPATH=src`). Sample suite `examples/suite_arithmetic.json`; `tests/test_suite.py` (15 tests).

**New metrics:** `latency_score` and `token_efficiency` in `src/agenteval/eval/metrics.py`. `Evaluator` now times each run; added `EvalCase.max_latency_seconds`, `EvalResult.elapsed_seconds`, `EvalReport.total_elapsed_seconds` / `mean_elapsed_seconds`. `token_efficiency` is NOT wired into the Evaluator: it needs `AgentState`/`llm.py` to capture Groq `usage_metadata`. No dollar-cost metric. Tests in `tests/test_eval.py`.

**State:** all uncommitted; black/ruff clean; **72 tests pass**.

**Problems hit:** None.

**Not done / next steps:**
1. Set `GROQ_API_KEY`; run example 01, the suite CLI with `--node groq`, and the API under uvicorn live.
2. Optional dollar-cost metric (token_efficiency is now wired).
3. LLM-as-judge scoring.
4. Commit this work.

---

## 2026-10-06 — Subagents, lint cleanup, safe `calculate`, multi-step tool loop

**Project subagents:** added four in `.claude/agents/` — `quality-check` (haiku, read-only), `metric-builder`, `tool-builder`, `session-logger` (sonnet). Committed as 78a74b5.

**Lint cleanup (a2d6575):** ran black + `ruff --fix` across `src`, `tests`, `examples`. The installed ruff enables a wider default rule set than plain E/F (I, UP, N, BLE, RUF...) with only `line-length` set in `pyproject.toml`. Added a per-file-ignore for N999 on the numbered `examples/*` scripts.

**Safe `calculate`:** `src/agenteval/agent/tools.py` no longer uses bare `eval`; it walks the AST and allows only numbers, unary +/-, `+ - * / // % **`. Exponent capped at 100 plus a bit-length cap for chained powers. Done by the tool-builder agent; tests added in `tests/test_agent.py`.

**Multi-step agent (roadmap item done):**
- `src/agenteval/agent/loop.py` — `create_tool_node`, `create_router`, `build_tool_agent(llm_node, registry, max_steps=10)` wiring llm -> (tools -> llm)* -> END.
- `src/agenteval/agent/llm.py` — `create_llm_node(model, tools=None)` binds the registry via `bind_tools` (OpenAI function format from `get_schema()`). Assistant messages are plain dicts with optional `tool_calls` `[{id, name, args}]`; the task is always prepended as a user message (it is not stored in `messages`). Tool results are `{"role": "tool", "tool_call_id", "content"}` dicts, which LangChain's `convert_to_messages` accepts, so `AgentState` stays plain dicts.
- `src/agenteval/agent/graph.py` — `AgentGraph` gained a `recursion_limit` attribute (default 25) passed to LangGraph invoke; `build_tool_agent` sets it to `2*max_steps+5` so our cap fires before `GraphRecursionError`.
- Error semantics: unknown tool / bad args go into `errors` (so `success_rate` drops) but the error text is fed back to the LLM and the loop continues. Tool-returned "Error: ..." strings (e.g. division by zero) are not agent errors. `current_step` counts LLM calls only. The `max_steps` cap is enforced by a `stop` node that appends an error. `EvalCase.max_steps` only affects `step_efficiency` scoring; the hard cap is the graph's `max_steps`.
- `tests/test_loop.py` — scripted mock LLM node, plus a `FakeChatGroq` monkeypatched into `llm.py` to test the real `llm_node` without a key. **47 tests pass** total.
- `examples/01_simple_agent.py` now also runs the tool loop when `GROQ_API_KEY` is set.

**Problems hit:**
- Agent files created mid-session were not loadable by name until Claude Code restarts; worked around by running them via a general-purpose agent told to read the `.md` file.
- The wider-than-expected ruff default rule set produced extra findings in the lint pass (see above).

**Published to GitHub:** renamed local `master` → `main` and created the public repo https://github.com/Nandangowdapc/agenteval (`origin`, tracking `origin/main`) via `gh repo create --source=. --push`. `.env` and `venv/` are not tracked.

**Paused here.** To resume: restart Claude Code so the `.claude/agents/` subagents load by name (check with `/agents`), then add `GROQ_API_KEY` to `.env` and run `examples/01_simple_agent.py` live.

**Not done / next steps:**
1. Set `GROQ_API_KEY` and run example 01 live. Untested risk: Groq/llama may emit malformed tool calls, in which case `langchain_groq` raises.
2. File-based (JSON/YAML) `EvalCase` suites / CLI.
3. LLM-as-judge and latency/cost metrics.
4. FastAPI layer.

---

## 2026-10-02 — Dependencies confirmed, evaluation layer built

**Dependencies:** ran `pip install -r requirements.txt` into the existing `venv/`. Everything was already satisfied — no fresh installs happened. `GROQ_API_KEY` setup was explicitly postponed by request, so `examples/01_simple_agent.py`'s live-LLM branch stays unexercised for now.

**Built the evaluation layer** (the part the README already claimed but didn't yet have code for):
- `src/agenteval/eval/metrics.py` — `exact_match`, `contains_match`, `tool_call_accuracy`, `step_efficiency`, `success_rate`. All plain functions, 0–1, higher is better.
- `src/agenteval/eval/evaluator.py` — `EvalCase` (task + optional expected output/tools + max_steps), `Evaluator` (runs an `AgentGraph` over a list of cases), `EvalResult`/`EvalReport` (per-case and aggregated scores, `summary()`).
- `tests/test_eval.py` — 7 tests, all against a **mock LLM node** (deterministic, no network) so the suite never needs `GROQ_API_KEY`. 13 tests total pass across the repo.
- `examples/02_evaluate_agent.py` — runnable demo with 3 cases, one of them deliberately wrong (expects "7" from "3 + 3") to prove scoring actually catches failures. Output: overall scores 1.00, 1.00, 0.60 — confirms the wrong case is correctly penalized.
- Wired the new types into `agenteval`'s top-level `__init__.py` exports and added an "Evaluation" section + usage example to `README.md`.

**No problems hit this session** — straightforward build, nothing to debug.

**Also created this session:** `CLAUDE.md` (standing architecture/decisions doc) and this `PROJECT_LOG.md`, mirroring the pattern from the `vocalcoach` project, per request.

**Not done / next steps:**
1. `GROQ_API_KEY` still not set — first thing to do when ready is copy `.env.example` → `.env` and add a free key, then actually run `examples/01_simple_agent.py` and try evaluating the *real* Groq-backed node (swap `mock_llm_node` for `create_llm_node()` in an eval case, per the note at the top of `02_evaluate_agent.py`).
2. The agent itself is still a single LLM node straight to `END` — no tool-calling loop or conditional branching yet, so `tool_call_accuracy` has nothing real to score against until that exists.
3. No FastAPI routes yet, despite the dependency being pinned.

---

## 2026-09-30 — Project scaffold created, Groq LLM node wired

**What was built:** initial LangGraph agent scaffold — `AgentState` (TypedDict with append-only reducers), `AgentGraph` (StateGraph wrapper), `ToolRegistry` with two example tools (`calculate`, mock `search`), and a Groq-backed `create_llm_node` (`llama-3.3-70b-versatile` default). Pinned dependencies to current stable releases in `requirements.txt`. Added `tests/test_agent.py` (6 tests, all passing), `examples/01_simple_agent.py`, `.env.example`, `README.md`, `.gitignore`.

**Not done:** no evaluation logic yet, despite the project being named/described as an evaluation framework — that's the scaffold only. No `GROQ_API_KEY` configured, so the live-LLM path in the example was never exercised this session.
