# Project Log

Running log for continuity across sessions. Newest entries at the top. See `CLAUDE.md` for the standing architecture summary.

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
