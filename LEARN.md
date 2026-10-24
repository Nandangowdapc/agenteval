# LEARN — The AgentEval Story

> The story of **what** AgentEval is, **why** every piece exists, and **how** it was built, told in the order it happened.
> You do not need an AI or programming background to follow the story. Engineers will still find every file name, function, field, command, number and trade-off they would need to rebuild the project or defend each decision.
>
> **Maintained by the `teacher` subagent** (`.claude/agents/teacher.md`). It is updated after every query that changes, explains, or decides something about the project. See [Teacher's Notebook](#teachers-notebook) for the running change-log.
>
> Sibling docs (and how they differ): `CLAUDE.md` = terse standing rules for the AI assistant. `PROJECT_LOG.md` = dated session diary. `README.md` = quick-start. **`LEARN.md` (this file) = the long-form "why and how" story.**

---

## Table of contents

- [How to read this story](#how-to-read-this-story)
- [Meet the cast](#meet-the-cast)
- [Prologue — The trouble with testing agents](#prologue--the-trouble-with-testing-agents)
- [The town at a glance (architecture)](#the-town-at-a-glance-architecture)
- [The toolbox: technology stack](#the-toolbox-technology-stack)
- [Chapter 1 — A new employee arrives (2026-09-30)](#chapter-1--a-new-employee-arrives-2026-09-30)
- [Chapter 2 — The examiner and the marking sheet (2026-10-02)](#chapter-2--the-examiner-and-the-marking-sheet-2026-10-02)
- [Chapter 3 — Helpers, a safety scare, and learning to use the toolbox (2026-10-06)](#chapter-3--helpers-a-safety-scare-and-learning-to-use-the-toolbox-2026-10-06)
- [Chapter 4 — Opening the front door: API, suites, CLI, more marking criteria (2026-10-14)](#chapter-4--opening-the-front-door-api-suites-cli-more-marking-criteria-2026-10-14)
- [Chapter 5 — A second opinion (2026-10-17)](#chapter-5--a-second-opinion-2026-10-17)
- [Chapter 6 — First day with the real brain (2026-10-22)](#chapter-6--first-day-with-the-real-brain-2026-10-22)
- [Chapter 7 — Teaching the employee to use the toolbox, and a fairer second opinion (2026-10-22)](#chapter-7--teaching-the-employee-to-use-the-toolbox-and-a-fairer-second-opinion-2026-10-22)
- [Chapter 8 — Who rents the brain? Staying a library, and swappable providers (2026-10-24)](#chapter-8--who-rents-the-brain-staying-a-library-and-swappable-providers-2026-10-24)
- [Chapter 9 — Clearing the task list: judge samples in the API, a calibration harness, and automatic checks (2026-10-24)](#chapter-9--clearing-the-task-list-judge-samples-in-the-api-a-calibration-harness-and-automatic-checks-2026-10-24)
- [Where everything lives (file-by-file)](#where-everything-lives-file-by-file)
- [How we test](#how-we-test)
- [Decision log](#decision-log)
- [Known limitations and risks](#known-limitations-and-risks)
- [Next steps](#next-steps)
- [Teacher's Notebook](#teachers-notebook)
- [Glossary](#glossary)

---

## How to read this story

Every chapter is one episode, in the order it happened, and follows the same five beats so you can skim or study:

| Beat | Question it answers |
|---|---|
| **The trouble** | What went wrong or was missing, in plain words? |
| **The idea** | What did we decide to try, and why this and not something else? |
| **How it was built** | The technical core: real file names, functions, a worked example. |
| **Did it work?** | What was verified (with real numbers), what was not, and what surprised us. |
| **Cliffhanger** | What this leaves open, leading into the next chapter. |

Paths are relative to the repo root. `src/agenteval/...` is the installable package. Anything marked "per the caller" was reported by the person running the live Groq runs and was not re-run by the teacher.

---

## Meet the cast

AgentEval is a small town of workers. Each part gets an everyday analogy, and then we name the real thing. We keep these analogies consistent for the whole story.

| In the story | What it really is | Where |
|---|---|---|
| **The employee (the agent)** | A program that gets a task and decides step by step what to do: answer, or use a tool. | `agent/` |
| **The employee's notebook** | `AgentState`, a plain dict of everything the agent remembers (messages, tool calls, errors...). | `agent/state.py` |
| **The workflow chart on the wall** | `AgentGraph`, a wrapper over LangGraph's `StateGraph`: boxes (nodes) joined by arrows (edges). | `agent/graph.py` |
| **The gadgets in the toolbox** | Tools: `calculate`, `search`, kept in a `ToolRegistry`. | `agent/tools.py` |
| **The employee's brain, rented from Groq (by default)** | The LLM node: a function that sends the conversation to a hosted model and returns its reply. | `agent/llm.py` |
| **The staffing-agency directory** | `PROVIDERS`: the list of services (Groq, OpenAI, Anthropic, Ollama) the brain can be rented from. | `agent/providers.py` |
| **The work routine** | The tool loop: think, use a gadget, think again, until done (or told to stop). | `agent/loop.py` |
| **The examiner** | `Evaluator`: gives the employee a task, watches, and marks the result. | `eval/evaluator.py` |
| **The marking criteria** | Metrics: `exact_match`, `contains_match`, `tool_call_accuracy`, `step_efficiency`, `success_rate`, `latency_score`, `token_efficiency`. | `eval/metrics.py` |
| **The exam papers** | `EvalCase`s, usually written as JSON/YAML "suites". | `eval/suite.py` |
| **The mark sheets** | `EvalResult` (one paper) and `EvalReport` (all papers). | `eval/evaluator.py` |
| **A second opinion from a different examiner** | The LLM-as-judge: another model grades fuzzy qualities. | `eval/judge.py` |
| **The reception desk** | The FastAPI layer: lets other programs request an evaluation over HTTP. | `api/` |
| **Understudies for rehearsals** | Mock LLM nodes and fake judges used in tests, so no real brain is rented. | `tests/` |
| **The town's helpers** | Claude Code subagents (`quality-check`, `metric-builder`, `tool-builder`, `session-logger`, `teacher`). | `.claude/agents/` |

**Where the analogies stop being accurate.** The "employee" has no memory between tasks: every run starts with a fresh notebook. The "brain" is not one person: it is a hosted model that can change or be retired (Chapter 6). The "second examiner" is also an LLM, so it can have its own biases, unlike a neutral human grader (Chapter 5 and 7).

---

## Prologue — The trouble with testing agents

### The world this project lives in

Modern "agentic" AI systems are programs where a large language model (LLM) does more than answer once. It **decides what to do next**: call a calculator, search the web, look at the result, decide again, and eventually produce an answer. Frameworks like **LangGraph** express this as a graph: nodes (steps) joined by edges (what runs next), with a shared **state** passed along.

### The pain

Agents are *non-deterministic* (the same task can go differently each time) and *multi-step*. That creates problems that ordinary unit tests don't solve:

1. **"Did it get the right answer?"** is not enough. An agent can reach `4` for `2+2` by calling a calculator once, or by looping eleven times and hitting errors. Both "pass" a naive check; only one is a good agent.
2. **Quality has many dimensions**: correctness, which tools it used, how many steps it took, how long it ran, how many tokens it burned (money), whether it errored, and sometimes fuzzy qualities ("is the explanation clear?") that no string comparison can judge.
3. **Results must be comparable and repeatable.** If you change a prompt or model, you need a score before and after, over the *same* set of tasks.
4. **Testing against a live LLM is slow, costs money/quota, needs an API key, and is non-deterministic.** A test suite that needs the internet is a test suite that gets skipped.

### The mission in one sentence

> Build a framework that **runs an agent over a suite of tasks, scores each run on several 0-1 metrics, and aggregates the results into a report**, usable from Python, a CLI, or an HTTP API, while keeping the whole thing testable without any API key.

### What "done" looks like (the goals)

- A real, small agent (LLM + tools + loop) to evaluate, built on LangGraph.
- A library of metrics, all with the same contract (float in `[0, 1]`, higher is better).
- A runner (`Evaluator`) and report objects (`EvalResult`, `EvalReport`).
- Ways to *define* tests as data (JSON/YAML suites), *run* them (CLI), and *serve* them (FastAPI).
- A fuzzy-quality metric (LLM-as-judge) that is opt-in.
- A test suite that never touches the network.

### Non-goals (deliberately out of scope)

- No database/persistence (SQLAlchemy is pinned in `requirements.txt` but **unused**).
- No dollar-cost metric (tokens are tracked; price per token is not).
- No multi-provider LLM support (Groq only, for now).
- No UI dashboard.

> This is a personal/portfolio project, so the emphasis is on clear design and honest engineering trade-offs rather than scale.

---

## The town at a glance (architecture)

### Two halves

```
                ┌───────────────────────────── THING UNDER TEST ─────────────────────────────┐
                │  agent/                                                                    │
                │   state.py  → AgentState (what the agent remembers)                        │
                │   graph.py  → AgentGraph (wraps LangGraph StateGraph; run(task))           │
                │   tools.py  → Tool, ToolRegistry, calculate, search                        │
                │   llm.py    → create_llm_node (Groq-backed "thinking" step)                │
                │   loop.py   → build_tool_agent: llm → (tools → llm)* → END                 │
                └────────────────────────────────────┬───────────────────────────────────────┘
                                                     │  final AgentState
                ┌────────────────────────────────────▼───────────────────────────────────────┐
                │  eval/                          THING THAT MEASURES                        │
                │   metrics.py   → pure scoring functions (0–1)                              │
                │   judge.py     → LLM-as-judge (needs a callable, not primitives)           │
                │   evaluator.py → EvalCase → run graph → scores → EvalResult → EvalReport   │
                │   suite.py     → load JSON/YAML cases, CLI                                 │
                └────────────────────────────────────┬───────────────────────────────────────┘
                                                     │
                ┌────────────────────────────────────▼───────────────────────────────────────┐
                │  api/   FastAPI: GET /health, GET /tools, POST /evaluate                   │
                └────────────────────────────────────────────────────────────────────────────┘
```

**Half 1 (`agent/`)**, the employee and their workplace, is a small but real agent. It exists so the framework has something genuine to evaluate.
**Half 2 (`eval/`)**, the examiner, is the actual product: the measuring machinery.
**`api/`**, the reception desk, is a thin HTTP shell over half 2.

### The life of one evaluation (follow one exam end to end)

1. You write an `EvalCase(task="What is 2 + 2?", expected_output="4", expected_tools=["calculate"])`.
2. `Evaluator.evaluate_case(case)` starts a timer and calls `graph.run(case.task)`.
3. `AgentGraph.run` builds a **fresh** initial `AgentState` (`create_initial_state`), compiles the LangGraph, and invokes it.
4. Inside the graph (tool-loop agent): the **llm node** asks Groq, Groq says "call `calculate` with `2 + 2`", the **router** sees tool calls, the **tools node** runs `calculate`, the result is appended as a `tool` message, back to the **llm node**, Groq says "4" with no tool calls, and the router returns `end`.
5. `Evaluator` reads the final state: last message = output, `tool_calls` = tools used, `current_step` = LLM calls, `errors`, `token_usage`.
6. It applies metrics: `exact_match`, `contains_match`, `tool_call_accuracy`, `step_efficiency`, `success_rate`, and (if configured) `latency_score`, `token_efficiency`, `llm_judge`.
7. The scores go into an `EvalResult`; `overall` is the mean of that case's scores. Many results form an `EvalReport`, whose `summary()` averages each metric across cases.

Hold that mental movie. Every file below is one frame of it, and the chapters that follow are the story of how each frame was added.

---

## The toolbox: technology stack

Each tool: what it is, what job it does here, and why it was picked.

| Tool | What it is | Its job in AgentEval | Why this one |
|---|---|---|---|
| **Python 3.11** | The language. | Everything. 3.11 gives `X \| None` union syntax and `list[str]` generics natively. | Standard for AI work; `requires-python = ">=3.11"` in `pyproject.toml`. |
| **LangGraph** (`StateGraph`) | A library for building agents as graphs of nodes/edges over a shared state. | The execution engine for the agent. `AgentGraph` wraps it. | It makes loops and branching explicit and inspectable instead of hiding them in a `while` loop. It also gives us **reducers** (see Chapter 1) for safely accumulating state. |
| **LangChain + `langchain-groq`** | LangChain is the LLM toolkit; `langchain-groq` is its adapter for Groq. | `ChatGroq` is how `llm.py` and `judge.py` actually call the model. | Gives a uniform `.invoke()` and `.bind_tools()` interface. |
| **Groq** | A cloud inference provider with a free tier and very fast hosted open models. | Hosts the models: agent default `openai/gpt-oss-120b`, judge default `qwen/qwen3.8-27b` (see Chapter 6). | **Free tier**: a portfolio project shouldn't need a paid key. |
| **FastAPI + uvicorn + pydantic** | FastAPI = web framework; uvicorn = server that runs it; pydantic = data validation. | The `api/` layer. Pydantic models validate request bodies automatically. | Auto-validation, auto OpenAPI docs, and a built-in **dependency injection** system that makes mocking trivial (see Chapter 4). |
| **python-dotenv** | Loads `KEY=value` lines from a `.env` file into environment variables. | Reads `GROQ_API_KEY` without hard-coding secrets. `.env` is git-ignored. | Standard secret-handling pattern. |
| **pytest** | Test runner. | The whole `tests/` suite (95 tests, re-run on 2026-10-22). | Plain `assert`, fixtures, and `monkeypatch`. |
| **black** | Opinionated code formatter. | Consistent formatting (`line-length = 88`). | Ends style arguments. |
| **ruff** | Very fast linter. | Catches bugs/unused imports/style issues. | One tool replaces flake8+isort+pyupgrade. |
| **SQLAlchemy** | ORM / database toolkit. | **Unused.** Pinned in anticipation of storing results. | Left in as a placeholder; honest about it in the docs. |
| **venv** | Per-project Python environment in `venv/`. | Isolates dependencies. | Standard; git-ignored. |

`requirements.txt` uses minimum versions (`>=`), e.g. `langgraph>=0.2`. Note from `CLAUDE.md`: when this was first installed, every version was *already present* in the repo's `venv/`, so `pip install -r requirements.txt` changed nothing. If dependencies ever drift, check the venv before assuming a fresh install is needed.

---

## Chapter 1 — A new employee arrives (2026-09-30)

Commit `0f3ae31`. 6 tests.

### The trouble
There is nothing to evaluate yet. Before building a measuring tool you need a *measurable thing*: an agent with state, nodes, tools, and an LLM. It is like opening an exam centre before hiring anyone to sit the exam.

### The idea
Hire a minimal employee: a LangGraph agent skeleton with four pieces: a state type (the notebook), a graph wrapper (the workflow chart), a tool registry (the toolbox), and a Groq LLM node (the brain). Plus project hygiene (`.gitignore`, `.env.example`, `README.md`, pinned dependencies, tests, one runnable example).

The choices we made, each told as "A or B":
- **Plain `TypedDict` vs Pydantic for the notebook.** A Pydantic model would add validation overhead and force nodes to build model instances. A `TypedDict` matches LangGraph's own idiom and lets nodes just return plain `dict`s. We chose `TypedDict`. (Pydantic is used where it earns its keep: the HTTP boundary.)
- **Wrapper vs raw `StateGraph`.** Exposing `StateGraph` directly is less code, but a wrapper gives one stable seam for the rest of the codebase (the `Evaluator` only needs `.run(task)`). We chose the wrapper.
- **Groq vs OpenAI/Anthropic.** The others may be stronger, but Groq has a free tier. "Groq-only for now" is an explicit scope limit, not an oversight.

### How it was built

#### Project layout and packaging
- `src/agenteval/` uses the **"src layout"**: the package lives under `src/`, so tests and scripts can't accidentally import the un-installed folder and hide a packaging mistake.
- `pyproject.toml` declares the package (`name = "agenteval"`, `version = "0.1.0"`, `requires-python = ">=3.11"`) and config for black/ruff.
- `.env.example` documents the one secret needed (`GROQ_API_KEY=`) without containing it; real keys go in `.env`, which `.gitignore` excludes (as it does `venv/`, `__pycache__/`, `results/`, `*.db`, ...).

#### `agent/state.py` — the notebook
`AgentState` is a `TypedDict`, a plain dict with declared keys:

| Key | Meaning |
|---|---|
| `messages` | Conversation history, append-only. |
| `tool_calls` | Every tool the agent requested, append-only. |
| `tool_results` | What each tool returned, append-only. |
| `token_usage` | Tokens per LLM call, append-only (added in Chapter 4). |
| `errors` | Problems encountered, append-only. |
| `reasoning` | Free-text current thought. |
| `current_step` | A counter: "how many LLM calls so far." |
| `task` | The original user task. |
| `metrics` | Scratch dict for performance numbers. |

**The key trick: reducers.** `Annotated[list[dict], add]` tells LangGraph: *when a node returns `{"messages": [x]}`, don't overwrite the field; combine old and new with `operator.add`* (list concatenation). Think of a notebook where you may only add new lines at the bottom, never erase. This is why a node can return just the **new** message and the history grows automatically. Fields without a reducer (`current_step`, `reasoning`) are simply overwritten.

`create_initial_state(task)` builds an empty state for a task. Every `run()` gets a fresh one, so no state leaks between evaluation cases.

#### `agent/graph.py` — `AgentGraph`, the workflow chart
A thin wrapper over `StateGraph(AgentState)` exposing `add_node`, `add_edge`, `add_conditional_edges`, `set_entry_point`, `compile`, and `run(task)`.

`run(task)` does three things in one call: compile, create fresh state, `invoke`. It passes `{"recursion_limit": self.recursion_limit}` so LangGraph's own safety cap is configurable.

**Why compile on every `run()`?** Compilation is cheap at this scale; caching the compiled graph would add invalidation complexity for no measurable gain. A conscious "not yet": revisit only if profiling says so.

#### `agent/tools.py` — the toolbox
- `Tool` = a name + a plain Python callable + a `description` + a JSON-schema-shaped `parameters` dict. Calling `tool(**kwargs)` calls the function.
- `ToolRegistry` = a dict of tools with `register`, `get`, `list_tools`, and `get_schema()`.
- `get_schema()` returns `{name: {"description": ..., "parameters": ...}}`, the shape you hand to an LLM so it knows what tools exist and how to call them ("function calling").
- A global `tool_registry` pre-registers two tools: `calculate` and `search` (a **mock** returning `"Mock search results for: ..."`).

**Why not LangChain's `@tool` decorator?** The registry is deliberately framework-agnostic. Tools are plain functions, so they're trivially unit-testable and not tied to LangChain.

#### `agent/llm.py` — the rented brain
`create_llm_node(model=DEFAULT_MODEL)` (originally `llama-3.3-70b-versatile`; Groq retired it, so since 2026-10-22 the default is `openai/gpt-oss-120b`, see Chapter 6) returns a **node function** `llm_node(state) -> dict`. A node is just "take state, return the *changes* to state."

Important behaviours:
- It reads `GROQ_API_KEY` (after `load_dotenv()`), and **raises immediately** with a setup hint if missing. *Fail fast*: a clear message at construction beats a confusing failure deep inside a LangGraph invoke.
- The task is **always prepended** as a user message and is **not** stored in `messages`. Reason: every LLM call needs the task, and storing it would duplicate it in the history.
- The node returns only deltas: the new assistant message and `current_step + 1`.

#### Tests and example
- `tests/test_agent.py` — state defaults, reducers, graph wiring, tool registry. 6 tests at this point.
- `examples/01_simple_agent.py` — demo that needs a real key.

### Did it work?
- Unit tests only. The real Groq path **was never run live** because the key setup was deliberately postponed. For three weeks of story this is the single biggest open risk in the project (see [Known limitations](#known-limitations-and-risks)).
- Honest gap noted that day: despite being called an *evaluation* framework, no evaluation logic existed yet.

### Cliffhanger
We have an employee, but nobody to mark their work. Next: the examiner.

---

## Chapter 2 — The examiner and the marking sheet (2026-10-02)

Committed as `b921f46` (2026-10-05). Tests: 13 total (7 new).

### The trouble
The README already *claimed* an evaluation framework, but no code scored anything. We needed a repeatable way to turn "an agent ran" into numbers.

### The idea
Two modules: **metrics** (pure scoring functions: the marking criteria) and **evaluator** (runs the exam papers and aggregates: the examiner). Plus a demo.

**Why free functions, not a `Scorer` class hierarchy?** Each metric needs only a couple of primitives and holds no state. A class hierarchy would be ceremony with no payoff. (When a metric needs *a callable*, as the LLM judge does, it lives in a separate module for exactly that reason, Chapter 5.)

**Design: `Evaluator(graph)` takes an already-wired graph, not a factory.** Since `AgentGraph.run()` builds fresh state each time, one graph instance can score many cases. Add a factory variant only if a node ever needs *case-specific* construction.

### How it was built

#### The metric contract
Every metric in `eval/metrics.py` is a free function returning a **float in `[0, 1]`, higher is better**. This single rule is what makes the rest easy: you can average any metrics together, compare runs, and set thresholds without special cases.

The original five:

| Metric | Inputs | Meaning |
|---|---|---|
| `exact_match(output, expected)` | two strings | 1.0 if equal after `.strip()`. Strict. |
| `contains_match(output, expected)` | two strings | 1.0 if `expected` appears anywhere in `output`, case-insensitive. Forgiving, and a good companion because LLMs add words ("The answer is 4"). |
| `tool_call_accuracy(called, expected)` | two lists of tool names | Fraction of *expected* tools that were actually called (set intersection). No expected tools means 1.0 (nothing to get wrong). |
| `step_efficiency(steps, max_steps)` | two ints | 1.0 at one step, falling **linearly** to 0.0 at `max_steps`. Rewards short paths. |
| `success_rate(errors)` | list of strings | 1.0 if no errors, else 0.0. |

Worked example of `step_efficiency` with `max_steps=5`: 1 step gives 1.0; 3 steps gives `1 − (3−1)/(5−1) = 0.5`; 5+ steps gives 0.0. Edge case `max_steps <= 1` is handled explicitly to avoid division by zero.

#### `eval/evaluator.py` — the three dataclasses (the paper and the mark sheets)
- **`EvalCase`** — a task plus what a good run looks like: `expected_output`, `expected_tools`, `max_steps`. Optional fields are `None`/empty so a case only gets scored on what it specifies. (Later chapters add `max_latency_seconds`, `max_tokens`, `judge_criteria`.)
- **`EvalResult`** — one case's outcome: the case, the **full final state** (kept so you can debug), `scores`, and an `overall` property = mean of the scores recorded for that case.
- **`EvalReport`** — all results; `overall` (mean of means), `mean_score(name)`, and `summary()` = mean of every metric that appeared + `overall`.

Why does `mean_score` average only over cases that *recorded* that metric? Because a case with no `expected_output` never gets an `exact_match`; counting it as 0 would unfairly punish it.

#### `Evaluator.evaluate_case` — the marking recipe
1. Run the graph on `case.task`.
2. If `expected_output` is set, score `exact_match` and `contains_match` against the last message's content (empty string if no messages).
3. If `expected_tools` is set, score `tool_call_accuracy` against names in `final_state["tool_calls"]`.
4. Always, score `step_efficiency` (from `current_step`) and `success_rate` (from `errors`).

#### Tests and the demo
- `tests/test_eval.py` runs against a **mock LLM node**, a plain function returning canned messages. This is the cornerstone testing decision (see [How we test](#how-we-test)): `pytest` never needs `GROQ_API_KEY`.
- `examples/02_evaluate_agent.py` has three cases, one **deliberately wrong** (expects `7` for `3 + 3`) to prove the scorer actually penalises failures. Result: overall scores 1.00, 1.00, 0.60. The 0.60 case still gets credit for tool use, step efficiency, and no errors but loses both match metrics, so the framework "catches" it.

> Caveat worth knowing: this example's *mock* node uses Python's `eval()` to compute the answer. That is acceptable only because it's a throwaway stand-in over hard-coded strings in an example; the real `calculate` tool **never** uses `eval` (see Chapter 3).

### Did it work?
The deliberately wrong case scored 0.60, as designed. But the log flagged a pitfall that day: the agent was still a single LLM node straight to `END`, so `tool_call_accuracy` had nothing real to measure.

### Cliffhanger
The examiner is ready, but the employee cannot actually use the toolbox, and the one gadget we have is dangerous. Next: the work routine, and a safety scare.

---

## Chapter 3 — Helpers, a safety scare, and learning to use the toolbox (2026-10-06)

Commits: `78a74b5` (subagents), `a2d6575` (lint), `5b1d1c8` (loop + safe calc), `a50444e` (log). Tests: 47.

This day had four threads: hiring helpers for chores, tidying the code, closing a security hole, and teaching the employee to use tools in a loop.

### Thread A — Project subagents (`.claude/agents/`)

**The trouble:** repetitive chores (run the lint+test gate, add a metric, add a tool, update docs) were being re-explained each time.
**The idea:** four Claude Code *subagents*, small specialist assistants defined in Markdown files with YAML frontmatter (`name`, `description`, `tools`, `model`) and a prompt body:

| Agent | Model | Allowed tools | Job |
|---|---|---|---|
| `quality-check` | haiku (cheap) | Bash, Read, Grep, Glob (read-only) | Run black, ruff, pytest via the repo venv; report pass/fail; **never fixes**. |
| `metric-builder` | sonnet | Read, Edit, Write, Bash, Grep, Glob | Add a metric end-to-end: function in `metrics.py`, tests, optional wiring in `Evaluator`. |
| `tool-builder` | sonnet | same | Add a tool to the registry with a correct JSON schema and tests. |
| `session-logger` | sonnet | Read, Edit, Bash, Grep, Glob | Append to `PROJECT_LOG.md` and refresh `CLAUDE.md` roadmap. |

Restricting each agent's `tools` is intentional least-privilege (a checker that can't edit can't "fix" a failure by weakening a test). Putting the cheap model on the mechanical job saves cost.
**Gotcha learned:** agent files created mid-session aren't loadable *by name* until Claude Code restarts; until then, run them through a general-purpose agent told to read the `.md`.

### Thread B — Lint cleanup
`black` + `ruff --fix` run over `src`, `tests`, `examples`. Discovery: the installed ruff enables a much wider default rule set than plain E/F (import sorting `I`, pyupgrade `UP`, naming `N`, blind-except `BLE`, `RUF`...) even with only `line-length` configured. One config tweak: ignore rule `N999` for `examples/*`, because numbered filenames like `01_simple_agent.py` aren't valid module names but are only ever *run*, never imported.

### Thread C — The safe `calculate` (security)

**The trouble:** the first `calculate` used Python's `eval()`. An LLM (or anyone controlling a prompt) can then execute arbitrary code: `__import__('os').system(...)`. In an agent that takes LLM output as tool input, that's remote code execution. It is like giving an employee a calculator that also happens to open any door in the building.

**The idea:** parse with `ast.parse(expression, mode="eval")` and **walk the syntax tree**, evaluating only whitelisted node types.

**How it was built (`tools.py`):**
- `_eval_node` accepts: numeric `Constant` (int/float, but **not** `bool`), unary `+`/`-`, and binary `+ - * / // % **`. *Anything else* (names, calls, attributes, strings) raises `_CalcError`.
- Operators come from `operator` via lookup tables (`_BINARY_OPS`, `_UNARY_OPS`), so there is no dynamic dispatch on user text.
- **Resource-exhaustion guards.** Safe from code execution still isn't safe from `9**9**9**9` eating all memory:
  - exponent magnitude capped at `_MAX_EXPONENT = 100`;
  - for int results, `left.bit_length() * abs(right) > 10_000` is rejected, which catches *chained* powers such as `((9**100)**100)**100` where each individual exponent looks innocent.
- `calculate()` turns every failure into a string beginning `Error: ...` (division by zero, invalid syntax, overflow, disallowed element) instead of raising.

**Why strings and not exceptions?** The result goes back to the LLM as text. An error message lets the model correct itself and retry.

### Thread D — The multi-step tool-calling loop

**The trouble:** a single LLM node can't *use* tools, so `tool_call_accuracy` was measuring fiction.

**The idea:** a real work routine: `llm → (tools → llm)* → END`. Think, use a gadget, think again, until the brain answers without asking for a gadget.

**How it was built: three pieces in `agent/loop.py`:**

1. **`create_tool_node(registry)`** looks at the last assistant message, and for each entry in its `tool_calls`:
   - unknown tool: append an error string to `errors` *and* feed `"Error: unknown tool '…'"` back as the tool result;
   - wrong arguments (`TypeError`): same pattern with `"Error: bad arguments…"`;
   - success: output string.
   Each result becomes `{"role": "tool", "tool_call_id": id, "content": output}` (the format LangChain's `convert_to_messages` accepts) plus an entry in `tool_results`.
2. **`create_router(max_steps)`** runs after every LLM call and returns one of three labels:
   - no tool calls: `"end"` (the LLM answered);
   - tool calls but `current_step >= max_steps`: `"stop"` (safety cap);
   - otherwise: `"tools"`.
3. **`build_tool_agent(llm_node, registry, max_steps=10)`** wires it: nodes `llm`, `tools`, `stop`; entry `llm`; conditional edges from `llm` using the router; `tools → llm`; `stop → END`. The `stop` node appends `"Stopped after N steps with tool calls pending"` to `errors`.

**Error semantics (a decision worth memorising):**
- *Agent* mistakes (unknown tool, bad args, hitting the cap) are recorded in `errors`, so `success_rate` drops. They measure the agent's quality.
- A tool *legitimately returning* `"Error: division by zero"` is **not** an agent error. The agent called a valid tool correctly; the user's maths was the problem. So it's returned as a normal result and the LLM can react to it.
- All errors, agent-caused or not, are *shown to the LLM* so the loop can recover rather than crash.

**`current_step` counts LLM calls only.** Tool executions don't increment it. That keeps `step_efficiency` meaning "how many times did we have to think."

**The recursion-limit puzzle.** LangGraph aborts runs that exceed `recursion_limit` supersteps (default 25) by raising `GraphRecursionError`. One loop iteration is *two* supersteps (llm + tools), so a `max_steps=10` agent could need ~20+. If LangGraph's cap fired before ours, the run would *crash* instead of ending gracefully with a recorded error. Fix: `AgentGraph.recursion_limit` became an attribute, and `build_tool_agent` sets it to `2 * max_steps + 5`, so our `stop` node always wins.

**Two different "max steps": don't confuse them.**
- `build_tool_agent(max_steps=…)` is the **hard cap** that actually stops the loop.
- `EvalCase.max_steps` only changes how `step_efficiency` is **scored**. It never stops anything.

**Binding tools in `llm.py`.** `create_llm_node(model, tools=registry)` calls `llm.bind_tools([...])`, converting `get_schema()` into OpenAI-style `{"type": "function", "function": {"name", "description", "parameters"}}` dicts. Assistant messages remain plain dicts with an optional `tool_calls: [{id, name, args}]`. This keeps `AgentState` plain-dict all the way down.

**Tests (`tests/test_loop.py`).** A *scripted* mock LLM node (returns a prepared sequence of responses) drives the loop deterministically, and a `FakeChatGroq` is **monkeypatched** into `llm.py` so the *real* `llm_node` code path is tested without a key.

### Thread E — Publishing
Local branch renamed `master` → `main`; public GitHub repo created via `gh repo create --source=. --push` (`origin/main`). `.env` and `venv/` are untracked. (This is why secrets hygiene matters in Chapter 6: the repo is public.)

### Did it work?
- 47 tests pass; black/ruff clean.
- **Untested risk (at the time):** real Llama-on-Groq models sometimes emit *malformed* tool calls, in which case `langchain_groq` itself may raise before our code sees anything. *Update 2026-10-22:* the live run (Chapter 6) worked with `openai/gpt-oss-120b`; no malformed-call crash was seen in the cases run, though that is a small sample.

### Cliffhanger
The employee can now use tools, safely, but you can only run the exam from Python. Who else might want to ask for an evaluation? Next: opening the front door.

---

## Chapter 4 — Opening the front door: API, suites, CLI, more marking criteria (2026-10-14)

Commits `5a402df` and `2d44639`. Tests: 72 then 83.

### Thread A — The reception desk: FastAPI layer (`api/`)

**The trouble:** being usable only from Python limits who/what can run evaluations (CI jobs, dashboards, other languages).
**The idea:** three endpoints: `GET /health`, `GET /tools`, `POST /evaluate`.

**How it was built:**
- `api/models.py` — pydantic models define the wire format: `EvalCaseIn` (with validation like `min_length=1`, `ge=1`), `EvaluateRequest` (cases + loop `max_steps` capped at 50), `CaseResultOut`, `EvaluateResponse`, `ToolOut`, `HealthResponse`. Invalid input is rejected with HTTP 422 before our code runs.
- `api/app.py` — `evaluate()` builds a tool agent, converts each `EvalCaseIn` into an `EvalCase`, runs the `Evaluator`, and maps the results into response models.

**The central trick: dependency injection.** The LLM node isn't hard-wired into the endpoint. It arrives through `Depends(get_llm_node_factory)`. In production that returns `groq_llm_node_factory`, which raises **HTTP 503** if `GROQ_API_KEY` is missing (503 = "service unavailable", the honest status for "I'm not configured"). In tests, `app.dependency_overrides[get_llm_node_factory] = lambda: mock_factory` swaps in a fake. Same endpoint code, zero network. (An understudy takes the stage in rehearsals.)

Smoke-tested live under uvicorn on 2026-10-17: `/tools` OK; `/evaluate` returned 503 with no key, as designed.

### Thread B — Exam papers as data (`eval/suite.py`)

**The trouble:** hard-coding `EvalCase` objects in Python makes suites awkward to share, diff, review, or write by non-programmers.
**The idea:** JSON/YAML files describing cases, validated on load.

**How it was built:**
- File shape: `{"name": ..., "cases": [ {task, expected_output, expected_tools, max_steps, max_tokens, judge_criteria} ]}`; a bare top-level list is also accepted.
- `load_suite(path)` returns `list[EvalCase]`. Validation is **strict and descriptive**: unknown fields are rejected (so a typo like `expected_ouput` fails loudly instead of silently dropping the check), `bool` is rejected where an int is required (because in Python `True` is an `int`), empty suites rejected, and every error is a `SuiteError` naming the file and case number.
- YAML needs the optional `pyyaml`; if absent you get a helpful message and JSON still works.
- **CLI:** `PYTHONPATH=src python -m agenteval.eval.suite examples/suite_arithmetic.json --node mock|groq [--judge none|groq]`. `--node mock` uses `_mock_llm_node`, which answers `What is <expr>?` via the real safe calculator, so a complete evaluation runs with **no API key**. Exit code `2` on a suite error.
- Sample: `examples/suite_arithmetic.json` (three arithmetic cases, one deliberately wrong).
- `tests/test_suite.py` — 15 tests.

(The `judge_criteria` field and `--judge` flag arrived in Chapter 5; they are listed here because the file shape is described in its final form.)

### Thread C — Two more marking criteria

| Metric | Formula | Wired how |
|---|---|---|
| `latency_score(elapsed, budget)` | `1 − elapsed/budget`, clamped to `[0,1]` | `Evaluator` now times each run with `time.perf_counter()`; scored only when `EvalCase.max_latency_seconds` is set. |
| `token_efficiency(tokens_used, budget)` | `1 − used/budget`, clamped | Scored only when `EvalCase.max_tokens` is set. |

Both share the "linear decay to zero at budget" shape and handle `budget <= 0` explicitly.

**Why token tracking needed new plumbing.** Tokens are only known *inside* the LLM response, so:
1. `AgentState` gained append-only `token_usage: Annotated[list[int], add]`.
2. `llm.py`'s `_total_tokens(response)` reads `response.usage_metadata["total_tokens"]` and returns `[n]`, or `[]` if the provider didn't report it (and explicitly rejects `bool`/non-int).
3. `Evaluator` sums the list into `tokens_used`; `EvalReport` exposes `total_tokens` / `mean_tokens`; `EvalReport` also exposes `total_elapsed_seconds` / `mean_elapsed_seconds`.

**Opt-in by design:** if you don't set `max_tokens` / `max_latency_seconds`, nothing changes. Existing behaviour and scores are untouched. This kept earlier tests valid.

**Not done:** converting tokens to **dollars** (would need a per-model price table).

### Did it work?
- Tests grew 72 then 83 (commit `5a402df` then `2d44639`).
- API: smoke-tested live without a key (see Thread A). Everything else verified through mocks only; no real Groq call yet.

### Cliffhanger
Some qualities, like "is this explanation clear?", can't be marked by comparing strings at all. Next: a second opinion.

---

## Chapter 5 — A second opinion (2026-10-17)

Commits `63df81b` and `d2abda0`. Tests: 92.

### The trouble
Some qualities can't be checked by string comparison: "Is the explanation clear?", "Is it polite?", "Does it mention the safety caveat?" There's no `expected_output` to match.

### The idea
Use *another LLM call* as a grader (the "LLM-as-judge" pattern): a second examiner. Ask it for a 0-10 rating against free-text criteria, then normalise to `[0, 1]` so it joins the other metrics.

**Why not put it in `metrics.py`?** Everything there takes primitives. The judge needs a callable (a dependency), so it has its own module.

### How it was built (`eval/judge.py`)
- **A judge is just a callable `str -> str`** (`Judge = Callable[[str], str]`): prompt in, reply out. That one decision makes it **injectable**: tests pass a fake lambda; production passes `create_groq_judge()`.
- `llm_judge(task, output, criteria, judge)` formats a fixed prompt (task, agent's answer, criteria, "rate 0-10, reply with only the number"), calls the judge, and parses the reply.
- `parse_score(reply, scale=10)` finds the **first number** with a regex, divides by `scale`, and clamps to `[0, 1]`. `"8"` gives 0.8; `"I'd say 7.5/10"` gives 0.75; `"15"` gives 1.0 (clamped); no number gives `None`.
- **Never raises:** an unparseable reply scores `0.0`. Rationale: one flaky judge response shouldn't abort a 200-case run. (Trade-off: a *systematic* parsing failure shows up as suspiciously low scores, not an error.)
- `create_groq_judge()` builds a `ChatGroq` at **temperature 0** (less randomness for grading), after the same fail-fast key check.

#### Wiring
- `EvalCase.judge_criteria: str | None`.
- `Evaluator(graph, judge=None)`: `llm_judge` is recorded **only if both** a judge **and** `judge_criteria` are present. Either missing means it is silently omitted.
- Suite files accept `judge_criteria` (non-empty string); CLI gets `--judge groq`.
- API: `EvalCaseIn.judge_criteria`, plus a second injectable dependency `get_judge_factory`. The judge is built **lazily, only if some case in the request has criteria**, so ordinary requests never need a judge, and without a key the endpoint returns 503 only when a judge is actually required.

### Did it work?
- Tested only with fake judges at this point. (As of 2026-10-22 the judge had still not run live until Chapter 7.)
- Known weaknesses of LLM judges (not yet mitigated, on the roadmap): **self-preference bias** (a model favours its own style), **position/verbosity bias**, and **variance** between runs. Planned mitigations: multiple samples averaged, and a structured rubric.

### Cliffhanger
Five chapters of mocks and fake judges. The real brain has never been rented. When the key finally arrives, what breaks first?

---

## Chapter 6 — First day with the real brain (2026-10-22)

Uncommitted at time of writing (`src/agenteval/agent/llm.py`, `src/agenteval/eval/judge.py`). Tests: 92, all passing (as reported by the caller).

### The trouble
Everything so far was verified only with mocks. The user finally supplied a `GROQ_API_KEY`, which exposed two things: a secret-handling slip, and the fact that the default model no longer existed.

### Thread A — Secrets: what `.env.example` is for
The key was first pasted into `.env.example` by mistake. It was moved into `.env` and `.env.example` was restored to its blank template (`GROQ_API_KEY=`).

| File | Committed to git? | Contains | Purpose |
|---|---|---|---|
| `.env.example` | **Yes** | Variable *names* with empty/placeholder values | Documentation: tells a new contributor which variables to set |
| `.env` | **No** (in `.gitignore`) | Real secret values | What `python-dotenv` actually loads at runtime |

The rule: **never put a real secret in a tracked file**. This repo is public on GitHub, and git history is permanent: even if a key is deleted in a later commit, it stays readable in the old one. Bots scrape public repos for keys within minutes. Here the mistake was caught before any commit, so nothing leaked; had it been committed, the correct response would be to revoke the key at the provider and issue a new one (rewriting history is not enough). The teacher did not read `.env` or verify its contents, deliberately; the move is as reported by the caller.

### Thread B — The model had been retired
The first live call returned `404 model_not_found` for `llama-3.3-70b-versatile`: Groq had retired it. Lesson: hosted model names are a *moving dependency*, unlike a library version you pin. The fix was to list the models the account can actually use via the Groq API and pick from that list, rather than guessing a name.

| Role | Constant | Old | New |
|---|---|---|---|
| Agent | `DEFAULT_MODEL` in `agent/llm.py` | `llama-3.3-70b-versatile` | `openai/gpt-oss-120b` |
| Judge | `DEFAULT_JUDGE_MODEL` in `eval/judge.py` | `llama-3.3-70b-versatile` | `qwen/qwen3.8-27b` |

**Why different families for agent and judge?** LLM judges show *self-preference bias*: a model tends to rate text in its own style higher. Using a judge from a different family (Qwen, trained by Alibaba) than the agent (gpt-oss, trained by OpenAI) reduces that. It is a partial mitigation only, and untested: bias remains possible.

**Why this and not something else?** Only the default constants were changed (no model-discovery step), which keeps the code simple; the cost is that retirement will happen again. Both are one-line edits.

### Thread C — Vocabulary that is easy to confuse
- **Groq** (with a q) = the company/service that *hosts and runs* models quickly on its own chips. This is who issues the API key (free tier).
- **Grok** (with a k) = xAI's own model family. Unrelated to Groq; we do not use it.
- **Model publisher prefix** (`openai/`, `qwen/`) = who *trained* the open-weight model. Groq downloads the published weights and serves them. So `openai/gpt-oss-120b` is OpenAI's open-weight model run by Groq, and no OpenAI or Alibaba account is involved. Only the Groq key is needed.

### Did it work?
Verified live (2026-10-22, per the caller):
- `examples/01_simple_agent.py`: the tool loop worked end to end; `calculate` computed 17*23+4 = 395.
- `pytest`: 92 passed (mocks, so unaffected by the model change).
- Suite CLI `--node groq` on `examples/suite_arithmetic.json`: overall score about 0.66. The `3+3=7` case is *deliberately wrong* (it tests that failures are detected). The `2+2` case scored `tool_call_accuracy` 0 because the model answered directly without calling the tool. That is a **real finding**: the metric works as intended, and it shows a capable model skips tools for trivial questions.

Not verified at that point:
- The **judge** had not run live: the suite has no `judge_criteria`, so `qwen/qwen3.8-27b` had never been called. Its reply format (for example any extra reasoning text before the number, which `parse_score`'s first-number regex could misread) was unknown.
- `/evaluate` live via the API was not reported as run.
- The teacher did not re-run the 0.66 suite result.

### Cliffhanger
The framework worked on real hardware, and it caught something: a capable model that skips the toolbox for easy questions. Is that the model's fault or our instructions'?

---

## Chapter 7 — Teaching the employee to use the toolbox, and a fairer second opinion (2026-10-22)

Uncommitted at time of writing (`agent/llm.py`, `eval/judge.py`, `eval/evaluator.py`, `eval/suite.py`, `tests/test_eval.py`, `tests/test_loop.py`). Tests: 95 passing (re-run by the teacher, and again when this story was rewritten). black/ruff clean as reported by the caller.

### The trouble
Chapter 6's live run exposed two weaknesses.
1. **The model skipped tools.** Asked `2+2`, the model answered from memory, so `tool_call_accuracy` was 0 for that case (0.33 averaged over the three-case arithmetic suite). The model was fine at maths; it just did not do what the evaluation expects, which is to use the tool.
2. **The judge was a known-biased, unmitigated component** (Chapter 5 listed this as planned work): a vague "rate 0-10" prompt and a single sample.

### Thread A — A tool-use system prompt (`agent/llm.py`)

**The idea:** tell the employee, in standing instructions, to use the toolbox. `create_llm_node(model, tools=None, system_prompt=None)`. New module constant `TOOL_SYSTEM_PROMPT` = "You have tools available. Always use a tool for arithmetic or lookups instead of answering from memory, then state the result."

**The choice, as A or B:** force tool use with `tool_choice="required"`, or nudge with a prompt. Forcing would make *every* turn call a tool, including the final answer turn, and would defeat the point of measuring whether the agent chooses tools well. A nudge keeps the agent's decision real while fixing an under-specified instruction. We chose the nudge. The honest flip side: this changes what the benchmark measures. We now score "does the model use tools when told to", not "does it independently decide to", so scores are not comparable with the pre-prompt 0.66 run.

**How it was built:**
- **Rule:** if `tools` is set and `system_prompt` is `None`, the default prompt is used. Pass your own string to override it. With no tools and no prompt, nothing is added (old behaviour).
- **Mechanism:** inside the node, after building `history = [user task, *messages]`, it does `history.insert(0, {"role": "system", "content": system_prompt})`. It is inserted on **every call** and never stored in `AgentState.messages`, for the same reason the task isn't stored (Decision 6): no duplication, and state stays a record of what the agent *did*.
- **Trade-off:** `history[0]` is now a system message, so the user task is `history[1]` and the first tool result is `history[3]`. `tests/test_loop.py` indices were shifted accordingly (it now asserts the system message equals `llm_module.TOOL_SYSTEM_PROMPT`).
- **Result (live, per the caller):** `tool_call_accuracy` rose from 0.33 to 1.0 on all three arithmetic cases.

### Thread B — Judge-bias mitigations (`eval/judge.py`, `evaluator.py`, `suite.py`)

**Rubric.** The prompt now defines bands: 0-2 wrong or irrelevant, 3-5 partly meets with major gaps, 6-8 mostly meets with minor flaws, 9-10 fully meets; and says "judge only against the criteria, not style or length". Anchoring each band reduces the judge's freedom to invent its own scale, and the style/length clause targets verbosity bias.

**Multi-sampling.** `llm_judge(task, output, criteria, judge, samples=1)` calls the judge `max(1, samples)` times with the same prompt, converts each reply to a score (unparseable gives 0.0, as before), and returns `statistics.median(scores)`.

Worked example (this is `test_llm_judge_median_of_samples`):

| Sample replies | Scores | Mean | Median (returned) |
|---|---|---|---|
| "2", "9", "8" | 0.2, 0.9, 0.8 | 0.633 | **0.8** |

**Median vs mean.** The mean is dragged by an outlier: one wild "2" pulls 0.633 below both sensible ratings. The median is the middle value after sorting, so one odd sample cannot move it. LLM judges produce occasional outliers (a misread, an off-format reply parsed as 0.0), which makes the median the more robust summary. With 2 samples the median equals the mean, so 3 or more is where robustness appears; odd N is cleanest.

**Why temperature 0 makes multi-sampling pointless.** *Temperature* controls randomness in token selection; at 0 the model picks its most likely token every time, so N calls return (essentially) the same reply and the median of N identical numbers is just that number: you pay N times for nothing. Sampling only helps when temperature > 0 so replies actually vary. Hence:
- `create_groq_judge(model, temperature=0.0)`: the default stays deterministic (single sample, reproducible).
- CLI `--judge-samples N`: with N>1 the CLI builds the judge at temperature 0.7, otherwise 0.0. The trade-off: more robust to one-off noise, but a rerun can differ slightly, and it costs N times the judge tokens.
- `Evaluator(graph, judge=None, judge_samples=1)` forwards `judge_samples` to `llm_judge`. Covered by `test_evaluator_passes_judge_samples` (three judge calls observed) and `test_judge_prompt_contains_rubric`.
- **Live (per the caller):** a run with 3 samples worked. This is also the first report of the judge itself running against real Groq. The teacher did not re-run it and has no data on how much scores moved.

**Remaining bias risks (not mitigated):**
1. **Criteria vs `expected_output` mismatch.** The judge sees only the criteria, never `expected_output`. If a case's criteria say one thing and its expected output another, the metrics will disagree and nothing flags it. Criteria must be written to agree with ground truth.
2. **Single judge model.** One judge (Qwen) has its own blind spots. Cross-family from the agent reduces self-preference but is not an independent panel.
3. **No calibration set.** We have never compared judge scores against human-labelled answers, so we do not know what "0.8" means in absolute terms. A small hand-labelled set to measure agreement is the missing piece.
4. The API does not expose `judge_samples` (only the Python `Evaluator` and the CLI do).

### Thread C — `/evaluate` verified live
The FastAPI app was run with uvicorn on a throwaway port with the real key. One `POST /evaluate` with `expected_tools` and `judge_criteria` returned (per the caller): overall 0.81, `calculate` called, `llm_judge` 1.0, 532 tokens. This confirms the injected factories work with a key present (the opposite of the 503 path) and the judge is wired through the API. It closes the "`/evaluate` live" gap from Chapter 6. A single request is a smoke test, not a correctness suite.

### Did it work?
- 95 tests pass (3 new in `tests/test_eval.py`; `test_loop.py` edited). All use mocks; the live claims above come from the caller, not from the teacher.
- Pitfall: changing a default prompt silently changes every future score. Treat prompt text like a versioned parameter and note it when comparing runs.
- Pitfall: `--judge-samples 3` with `--judge groq` triples judge calls; mind free-tier rate limits.

### Cliffhanger
Every component has now met the real world at least once, in small samples. What is still open: a calibration set to learn what the judge's scores really mean, `judge_samples` in the API, and nothing from this chapter has been committed yet. See [Next steps](#next-steps).

---

## Chapter 8 — Who rents the brain? Staying a library, and swappable providers (2026-10-24)

### The trouble
Two questions arrived together.

First, a question about shape: should AgentEval become a public website where anyone can try it? Second, a question about lock-in: so far the employee's brain was always rented from one company, Groq. If a developer already pays for OpenAI or Anthropic, or wants to run a model on their own laptop, the code gave them no way in. The Groq name was baked into `llm.py`, `judge.py`, the API and the CLI.

### The idea
**Decision 1: stay a Python library, no public website.** We weighed two options:
- *A public site*: friendly for visitors, but every visitor's evaluation would spend the author's Groq key. That means key abuse and quota exhaustion (the free tier is limited), plus ongoing upkeep (hosting, rate limiting, security).
- *A library*: a developer installs it and puts **their own** key in their own `.env`. Nobody ever uses the author's key, and there is nothing to keep running.

We chose the library. (The `api/` layer still exists, but it is something you run yourself, with your own key.)

**Decision 2: let developers switch providers, with Groq still the default.** The idea is a small **registry** (a lookup table) of providers. Think of it as a staffing agency directory: the employee's brain can be rented from any listed agency, and the town works the same whichever one is chosen. This works because LangChain's chat classes for all these services share one interface (`.invoke()`, `.bind_tools()`, `usage_metadata`), so the rest of the code does not care which one it holds. The analogy stops here: the brains are not interchangeable in quality. A different model can behave differently on the same exam, so scores from different providers are not directly comparable.

Trade-off we accepted: each non-Groq provider needs its own package. Rather than force everyone to install all of them, imports are **lazy** (done only when that provider is chosen) and the packages are **optional extras**.

### How it was built

#### `agent/providers.py` (new)
- `Provider`: a frozen dataclass with `name`, `env_var` (the API-key variable, `None` if no key needed), `default_model`, `default_judge_model`, `signup_hint`, `extra` (the pip extra name) and `factory` `(model, api_key, temperature) -> chat model`.
- `PROVIDERS`: the registry, `groq`, `openai`, `anthropic`, `ollama`. Each factory (`_groq`, `_openai`, `_anthropic`, `_ollama`) imports its LangChain class inside the function, so `langchain_openai` is only needed if you pick OpenAI. `_temp` adds `temperature` only when one was given.
- `get_provider(name=None)`: resolution order is **explicit name, then `$AGENTEVAL_PROVIDER`, then `groq`**. Case-insensitive. An unknown name raises `ValueError` listing the valid choices.
- `create_chat_model(provider, model, temperature, judge=False)`: looks up the provider, **fails fast** if its key variable is unset (`RuntimeError` with the signup hint, same philosophy as Chapter 1), picks `default_judge_model` when `judge=True` else `default_model`, then calls the factory. If the LangChain package is missing, the `ImportError` is re-raised with the hint `pip install 'agenteval[<extra>]'`. Ollama has `env_var=None`, so it needs no key.

Default models per provider (agent / judge): groq `openai/gpt-oss-120b` / `qwen/qwen3.8-27b`; openai `gpt-4o-mini` / `gpt-4o`; anthropic `claude-haiku-5-5` / `claude-sonnet-5-5`; ollama `llama3.1` / `qwen2.5`. Each provider has a *different* judge default than its agent default, to keep the Chapter 5/6 self-preference defence.

#### Rewiring the existing files
- `agent/llm.py`: `create_llm_node(model=None, tools=None, system_prompt=None, provider=None)`. It no longer imports `ChatGroq` or reads `GROQ_API_KEY` itself; it calls `create_chat_model(provider, model)`. `DEFAULT_MODEL` is now derived from `PROVIDERS["groq"]`. Tool binding and the system prompt are unchanged.
- `eval/judge.py`: new `create_judge(provider=None, model=None, temperature=0.0)` (uses `judge=True`). `create_groq_judge(model, temperature)` is kept as a thin wrapper calling `create_judge("groq", ...)`, so old code still works.
- `eval/suite.py` CLI: new `--provider`, `--model`, `--judge-provider`, `--judge-model`. `--node` and `--judge` now accept `llm`; `groq` stays as an alias meaning the same thing (the default provider, or `--provider` if given). The judge provider falls back to `--provider`, then to the default. `build_graph(node, provider=None, model=None)` gained those arguments.
- `api/app.py`: the factories now call the generic builders and convert `RuntimeError` (missing key) into HTTP 503, replacing the hand-written `os.environ` check. So the API honours `$AGENTEVAL_PROVIDER` too.
- `pyproject.toml`: `[project.optional-dependencies]` with `openai`, `anthropic`, `ollama` extras. Groq stays in `requirements.txt` as the base. `.env.example` got `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` placeholders (names only); the README gained a providers table.

Worked example:
```bash
# default: Groq, as before
PYTHONPATH=src python -m agenteval.eval.suite examples/suite_arithmetic.json --node llm
# switch the agent to OpenAI and keep the judge on Groq
PYTHONPATH=src python -m agenteval.eval.suite examples/suite_arithmetic.json \
  --node llm --provider openai --judge llm --judge-provider groq
# or set it once for everything
AGENTEVAL_PROVIDER=ollama
```

### Did it work?
- 107 tests pass (verified with `venv/Scripts/python -m pytest -q`); black and ruff clean (per the caller). New `tests/test_providers.py` has 11 test functions (12 collected, one is parametrized): registry and default, resolution order, unknown provider, missing-key hint per provider, Ollama needing no key, default vs judge models, missing-extra hint, `create_judge` passing provider and temperature, and the CLI failing cleanly when a key is missing. Existing tests in `test_eval.py` and `test_loop.py` now monkeypatch `langchain_groq.ChatGroq` (the class's new import location, since `llm.py` no longer holds it at module level).
- Live (per the caller): the Groq suite CLI re-ran fine (overall 0.68, `tool_call_accuracy` 1.0); `--provider openai` with no key printed the clean setup hint instead of a stack trace.
- **Not verified:** the OpenAI, Anthropic and Ollama paths are **mock-tested only**; no live call was made. Their default model IDs were **not checked against the providers' docs** and may be wrong or stale. Treat them as placeholders. This is the same lesson as Chapter 6: tests cannot catch a retired or misspelled model name.
- Pitfall: scores across providers are not comparable (see Chapter 7's note on prompt changes; a model change is a bigger version of that).

### Cliffhanger
The brain is now swappable, but only Groq has ever really been run. Next: verify the other providers' model IDs and a real run each, then still the judge calibration set and `judge_samples` in the API. See [Next steps](#next-steps).

---

## Chapter 9 — Clearing the task list: judge samples in the API, a calibration harness, and automatic checks (2026-10-24)

The same day as Chapter 8, after commit `feb181d`, the author said: "do everything possible for now sequentially" on the remaining list. Four small jobs followed, in order. None is committed yet.

### The trouble
- Chapter 7 gave the second examiner (the judge) the ability to answer several times and take the middle score (`judge_samples`), but only the command line could use it. The front desk (the API) could not.
- We had never checked whether the judge's marks match what a person would give. Without that, "judge score 0.8" has no known meaning.
- Nothing checked the code automatically. Every quality check (formatting, lint, tests) ran only when someone remembered to.
- A tiny formatting slip in `CLAUDE.md`: roadmap items 5 and 6 had been run together on one line.

### The idea
1. **Fix the formatting** in `CLAUDE.md` (trivial).
2. **Let the API ask for judge samples**, with limits so a caller cannot request 500 judge calls.
3. **Build a calibration harness**: a small tool that feeds the judge examples with known human marks and measures how close it gets. Calibration here means "checking a measuring instrument against a known reference", like weighing a 1 kg weight on a new kitchen scale.
4. **Add CI** (continuous integration: a robot that re-runs the checks on every push), using no API keys at all.

### How it was built

#### Thread A: `judge_samples` in the API
- `api/models.py`: `EvaluateRequest.judge_samples: int = Field(default=1, ge=1, le=5)`. Outside 1 to 5, FastAPI answers **422** (unprocessable request) before our code runs.
- `api/app.py`: the type `JudgeFactory` changed from `() -> Judge` to `temperature -> Judge`. In `evaluate()`:
```python
judge = None
if any(c.judge_criteria for c in request.cases):
    judge = judge_factory(0.7 if request.judge_samples > 1 else 0.0)
report = Evaluator(graph, judge=judge, judge_samples=request.judge_samples).evaluate(...)
```
- **Why the factory needed a temperature.** Chapter 7's lesson: asking a temperature-0 judge five times just repeats one answer, so the median of five identical numbers is pointless. The API must therefore *build* the judge hotter (0.7) when more than one sample is wanted. The default factory `groq_judge_factory(temperature=0.0)` passes it on to `create_judge(temperature=...)`. The judge is still only built when some case has `judge_criteria`, and a missing key still becomes 503.
- Trade-off: changing the factory's signature broke the one existing test override (`lambda: lambda: judge` became `lambda: lambda _t: judge`). We accepted that small break because the alternative (leaving temperature fixed) would make the new field useless.
- Tests (3 new in `tests/test_api.py`): replies `"2","9","8"` with `judge_samples=3` give median 0.8 and the factory is called once with 0.7; default requests call the factory with 0.0; `judge_samples=6` gives 422.

#### Thread B: `eval/calibration.py` (new)
Think of it as a trial exam for the examiner: we hand the judge answers whose "true" marks a person already wrote down, then see how far off it is.

- **Input file** (`examples/judge_calibration.json`, 14 seed items): a JSON list of `{task, output, criteria, human_score}` with `human_score` on the judge's own 0 to 10 scale.
- `load_calibration(path)` validates strictly and raises `CalibrationError` (a `ValueError`) for: unreadable or invalid JSON, not a list, fewer than 2 items (correlation needs at least two points), a non-object item, an empty `task`/`output`/`criteria`, a `human_score` that is a bool (Python counts `True` as a number, so it is rejected explicitly), not a number, or outside 0 to 10. Scores are divided by 10 into a `CalibrationItem`.
- `calibrate(items, judge, samples=1)` runs the existing `llm_judge(...)` per item and returns a `CalibrationReport`.
- `CalibrationReport` properties, all on the 0 to 1 scale:
  - `mean_abs_error`: average distance between judge and human (lower is better).
  - `bias`: average of (judge minus human). Positive means the judge is lenient, negative means strict.
  - `agreement`: share of items where the judge is within `AGREEMENT_TOLERANCE = 0.2` (two points on the 10-point scale) of the human; a `1e-9` slack avoids floating-point surprises at exactly 0.2.
  - `correlation`: Pearson r (do the two rise and fall together?) via `statistics.correlation`; returns `None` if either list is constant, since r is undefined then.
- `format_report` prints one line per item plus the summary. CLI:
```bash
PYTHONPATH=src python -m agenteval.eval.calibration examples/judge_calibration.json \
  [--judge-provider groq] [--judge-model M] [--judge-samples N]
```
  Exit code 2 with a message on a bad file. As elsewhere, N>1 samples builds the judge at temperature 0.7, else 0.0. It reuses `PROVIDERS` and `create_judge` from Chapter 8, so any provider works.
- Tests: `tests/test_calibration.py`, 14 tests (verified by running it).

#### Thread C: `.github/workflows/ci.yml` (new)
On push to `main` and on pull requests: Python 3.11 on `ubuntu-latest`, `pip install -r requirements.txt pyyaml httpx`, then `black --check src tests`, `ruff check src tests`, `pytest -q`. **No API keys are set**, on purpose: this is Chapter 2's rule (tests never need a key) turned into an enforced check. `pyyaml` and `httpx` are installed explicitly (suite YAML loading and FastAPI's test client) in case the requirements file does not pull them in.

### Did it work?
- **Tests:** 124 pass (verified now with `venv/Scripts/python -m pytest -q`; was 107): +3 in `test_api.py`, +14 in `test_calibration.py`. Black and ruff clean (per the caller).
- **Live calibration run (per the caller, default Groq judge `qwen/qwen3.8-27b`, 14 items):** mean absolute error **0.100**, bias **-0.071**, agreement **86%**, correlation **0.884**. So the judge tracks the labels well and runs slightly strict. The two telling misses: it gave **0** to approximate-but-reasonable answers, for instance "around 140" (human 3) and "about one metre" (human 8). The judge punishes approximation more than the author did.
- **The important caveat, stated plainly:** the human labels were written by the **AI assistant that is the author of this code, not by an independent panel of people**. So this is a working harness plus a smoke test, **not a real calibration**. An r of 0.884 shows the judge agrees with *those labels*, which may carry the same blind spots as the assistant. A genuine calibration needs labels from several independent people. This is the same family of self-agreement risk as Chapter 5's self-preference bias.
- **Not verified:** the CI workflow has **never run on GitHub**; nothing was pushed (pushing was not authorised). It mirrors commands that pass locally, but a first real run could still fail, for example on a missing package.
- **Not done:** `sqlalchemy` is still pinned in `requirements.txt` but unused; removing it needs the user's decision. No live test of any non-Groq provider (needs the user's own key).
- **A small slip, recorded for honesty:** the first attempt to create several files with one shell command failed to parse and wrote nothing; the files were then re-created with the Write tool. No wrong content reached the repo.

### Cliffhanger
The harness exists but its reference answers are only one author's opinion. Real next steps: independent human labels, an actual first CI run after a push, a decision on `sqlalchemy`, and the live check of the other providers. See [Next steps](#next-steps).

---

## Where everything lives (file-by-file)

### Root
| File | Purpose |
|---|---|
| `CLAUDE.md` | Standing project instructions + design decisions for the AI assistant; read automatically each session. Terse. |
| `PROJECT_LOG.md` | Dated diary, newest first, maintained by `session-logger`. |
| `LEARN.md` | This story; maintained by `teacher`. |
| `README.md` | Quick-start, layout, evaluation overview. |
| `pyproject.toml` | Package metadata; black/ruff config; N999 ignore for examples; optional extras `openai`, `anthropic`, `ollama` (Chapter 8). |
| `requirements.txt` | Dependencies (minimum versions). |
| `.env.example` | Committed template: variable names only, never real values. Real `.env` is git-ignored (see Chapter 6). |
| `.github/workflows/ci.yml` | CI: black --check, ruff, pytest on push to main and PRs; no keys; not yet run on GitHub (Chapter 9). |
| `.gitignore` | Excludes venv, caches, `.env`, `results/`, `*.db`, IDE folders. |

### `src/agenteval/`
| File | Key contents | Chapter |
|---|---|---|
| `__init__.py` | Re-exports `AgentGraph`, `AgentState`, `EvalCase`, `EvalReport`, `EvalResult`, `Evaluator`; `__version__`. | 1-2 |
| `agent/state.py` | `AgentState`, `create_initial_state`. | 1 (+tokens in 4) |
| `agent/graph.py` | `AgentGraph` with `run()` and `recursion_limit`. | 1 (+limit in 3) |
| `agent/tools.py` | `Tool`, `ToolRegistry`, safe `calculate`, mock `search`, global `tool_registry`. | 1 (safe calc in 3) |
| `agent/llm.py` | `create_llm_node(model, tools, system_prompt, provider)`, `TOOL_SYSTEM_PROMPT`, `_total_tokens`. | 1 (+tools in 3, +tokens in 4, +model change in 6, +system prompt in 7, +provider in 8) |
| `agent/providers.py` | `Provider`, `PROVIDERS`, `get_provider`, `create_chat_model`; lazy per-provider imports. | 8 |
| `agent/loop.py` | `create_tool_node`, `create_router`, `build_tool_agent`. | 3 |
| `eval/metrics.py` | Seven metric functions. | 2 (+2 in 4) |
| `eval/evaluator.py` | `EvalCase`, `EvalResult`, `EvalReport`, `Evaluator(graph, judge, judge_samples)`. | 2 (extended 4, 5, 7) |
| `eval/judge.py` | `Judge`, `parse_score`, `llm_judge(..., samples)`, `create_judge(provider, model, temperature)`, `create_groq_judge` (wrapper); rubric prompt. | 5 (+model in 6, +rubric, sampling in 7, +create_judge in 8) |
| `eval/suite.py` | `load_suite`, `SuiteError`, `build_graph`, `format_report`, CLI `main` (`--node`, `--provider`, `--model`, `--judge`, `--judge-provider`, `--judge-model`, `--judge-samples`). | 4 (+judge 5, +samples 7, +providers 8) |
| `eval/calibration.py` | `load_calibration`, `CalibrationError`, `calibrate`, `CalibrationReport` (MAE, bias, agreement, correlation), `format_report`, CLI. | 9 |
| `api/app.py` | FastAPI app, DI factories (RuntimeError -> 503), three routes; `JudgeFactory` is `temperature -> Judge`. | 4 (+judge 5, +providers 8, +temperature 9) |
| `api/models.py` | Pydantic request/response models; `EvaluateRequest.judge_samples` (1-5). | 4 (+9) |

### `tests/`, `examples/`
See [How we test](#how-we-test). `examples/`: `01_simple_agent.py` (live, needs key; also runs the tool loop), `02_evaluate_agent.py` (mock, no key), `suite_arithmetic.json` (sample suite), `judge_calibration.json` (14 seed items with human scores, written by the AI author; Chapter 9).

### `.claude/agents/`
`quality-check.md`, `metric-builder.md`, `tool-builder.md`, `session-logger.md`, **`teacher.md`** (this story's maintainer).

---

## How we test

**Rule: `pytest` must pass with no network and no API key.** (The understudies perform; the real brain is never rented in tests.)

How each layer achieves that:

| Layer | Technique |
|---|---|
| Metrics | Pure functions, so direct asserts on edge cases (0 budget, empty lists, clamping). |
| Evaluator | A **mock LLM node** (plain function returning canned state deltas). |
| Tool loop | A **scripted** mock node (returns a prepared sequence) to force exact tool-call paths, including unknown tools, bad args, and hitting the cap. |
| Real `llm_node` | A **`FakeChatGroq`** substituted via `monkeypatch`, so the real code that builds messages and reads `usage_metadata` runs without a network call. |
| Providers | `monkeypatch` of env vars and of `langchain_groq.ChatGroq` / import failures; asserts on resolution order, setup hints and default models. No network. |
| API | `app.dependency_overrides` replace the LLM and judge factories; FastAPI's test client drives requests. |
| Judge | Fake judge callables returning fixed strings (`"8"`, `"garbage"`); an iterator of replies (`"2","9","8"`) to test the median; a recording lambda to assert the prompt contains the rubric and that `judge_samples` triggers N calls. |
| Suites | Temp files via pytest fixtures, valid and invalid. |

**Test-count progression:** 6 (Chapter 1) → 13 (Chapter 2) → 47 (Chapter 3) → 72 → 83 (Chapter 4) → 92 (Chapter 5) → 95 (Chapter 7; the final +3 are the judge rubric/median/`judge_samples` tests, 2026-10-22; 92 was unchanged by the Chapter 6 model change) → 107 (Chapter 8; +12 collected from `tests/test_providers.py` (11 test functions, one parametrized), 2026-10-24; verified by running pytest) → 124 (Chapter 9; +3 in `test_api.py`, +14 in `tests/test_calibration.py`, 2026-10-24; verified by running pytest). CI (Chapter 9) now runs black, ruff and pytest on every push, but has not yet run on GitHub. Tests mock the LLM, so a retired model could never fail them, which is also why they could not have caught it. Likewise the tool-use prompt fix could only be *seen* live; the mocked test just asserts the system message is sent.

**The honest limitation:** green tests prove the *plumbing* is right, not that real Groq behaves. As of 2026-10-22 the agent tool loop, suite CLI, judge (3-sample run) and `/evaluate` have each been run live (per the caller). Never claim more.

Quality gate (what `quality-check` runs): `black --check`, `ruff check`, `pytest`, via the repo's `venv`, never the global Python.

---

## Decision log

One-liners; the reasoning is in the chapters.

| # | Decision | Reason | Chapter |
|---|---|---|---|
| 1 | `AgentState` is a `TypedDict` with `add` reducers | LangGraph idiom; nodes return plain dicts | 1 |
| 2 | `AgentGraph` wraps `StateGraph` | Stable seam; central place for `recursion_limit` | 1 |
| 3 | Compile on every `run()` | Cheap; caching not worth complexity yet | 1 |
| 4 | Tool registry, no `@tool` decorator | Framework-agnostic, easy to test | 1 |
| 5 | Groq-only LLM node | Free tier | 1 |
| 6 | Task prepended each call, not stored in `messages` | Avoid duplication; every step needs it | 1 |
| 7 | `calculate` uses AST walking, never `eval` | Security: LLM output is untrusted | 3 |
| 8 | Agent errors go to `errors`; tool `"Error:"` strings do not | Measures agent quality, not user mistakes | 3 |
| 9 | `recursion_limit = 2*max_steps + 5` | Ensure our graceful stop wins over LangGraph's crash | 3 |
| 10 | Metrics are free functions, 0-1, higher is better | Uniform, averageable, no needless classes | 2 |
| 11 | `Evaluator` takes a wired graph, not a factory | `run()` already makes fresh state | 2 |
| 12 | Judge = injectable `str -> str` callable | Testable; swappable provider | 5 |
| 13 | Unparseable judge reply scores 0.0, never raises | One bad reply must not abort a run | 5 |
| 14 | API deps injected (`get_llm_node_factory`, `get_judge_factory`) | Mockable tests; 503 when unconfigured | 4, 5 |
| 15 | Optional metrics are opt-in (only scored when the budget/criteria is set) | Backwards compatible; no penalty for cases that don't care | 4 |
| 16 | Suite validation is strict | Typos fail loudly | 4 |
| 17 | Tests use mocks; real Groq only in examples | `pytest` needs no key | 2 |
| 18 | Agent default `openai/gpt-oss-120b` (2026-10-22) | Old Llama model retired by Groq (404) | 6 |
| 19 | Judge default `qwen/qwen3.8-27b`, different family from agent | Reduce self-preference bias | 6 |
| 20 | `.env.example` holds names only; secrets only in git-ignored `.env` | Public repo; git history is permanent | 6 |
| 21 | Default `TOOL_SYSTEM_PROMPT` when tools are bound (2026-10-22) | Model answered `2+2` from memory; `tool_call_accuracy` 0.33 -> 1.0. Prompt nudge over forced `tool_choice` | 7 |
| 22 | System prompt injected per call, not stored in state | Same reasoning as decision 6 | 7 |
| 23 | Judge prompt has explicit 0-2/3-5/6-8/9-10 rubric, judge on criteria only | Anchor the scale; reduce style/length bias | 7 |
| 24 | `samples` gives median, not mean | Robust to one outlier rating | 7 |
| 25 | Judge temperature 0 by default; CLI uses 0.7 only when `--judge-samples` > 1 | Sampling is pointless at temperature 0 | 7 |
| 26 | Stay a Python library; no public website (2026-10-24) | A public site would spend the author's Groq key (abuse, quota) and need upkeep; library users bring their own key | 8 |
| 27 | Provider registry (`providers.py`); Groq stays default; resolution: explicit > `$AGENTEVAL_PROVIDER` > groq | Let developers switch LLM APIs without touching code | 8 |
| 28 | Lazy provider imports; non-Groq packages are optional extras | No forced install of unused packages | 8 |
| 29 | Fail fast on missing key (`RuntimeError`) and missing package (`ImportError` with pip hint) | Clear setup hint instead of a deep LangGraph error; API maps `RuntimeError` to 503 | 8 |
| 30 | Judge default model differs from agent default within every provider | Keep self-preference defence (decision 19) | 8 |
| 31 | `--node/--judge` accept `llm`; `groq` kept as alias; `create_groq_judge` kept as wrapper | Backwards compatibility | 8 |
| 32 | `judge_samples` in the API, limited to 1-5 (422 outside) | Parity with CLI; cap bounds cost per request | 9 |
| 33 | API `JudgeFactory` takes a temperature; 0.7 if samples > 1 else 0.0 | Sampling a temperature-0 judge repeats one answer (decision 25) | 9 |
| 34 | Calibration harness as a separate module/CLI, requires >= 2 items, rejects bool scores, correlation `None` if constant | Pearson r undefined otherwise; fail loudly on bad data | 9 |
| 35 | CI runs with no API keys | Enforces decision 17 | 9 |
| 36 | `sqlalchemy` left pinned though unused | Removal needs the user's decision | 9 |

---

## Known limitations and risks

1. **Live-verified (2026-10-22, per the caller):** tool loop, suite CLI, judge (3 samples) and `/evaluate` ran against Groq, each in small samples. Malformed tool calls remain a possible risk (none seen).
2. **Hosted model names can be retired** without notice (happened to Llama 3.3); defaults need occasional checking.
3. **Judge bias/variance** partly mitigated (cross-family judge, rubric, median of N samples), but the only calibration set (`examples/judge_calibration.json`, 14 items) was **labelled by the AI author, not independent humans**, so it is a smoke test, not a real calibration (live: MAE 0.100, bias -0.071, agreement 86%, r 0.884, per the caller; the judge is strict on approximate answers). Also a single judge model and possible criteria/`expected_output` mismatch. The API now exposes `judge_samples` (1-5).
4. **`search` is a mock.** `tool_call_accuracy` against it is fine, but answers aren't real.
5. **No dollar-cost metric**; **no persistence** (SQLAlchemy unused).
6. **Evaluation is sequential**: one case at a time, no concurrency.
7. `step_efficiency` can't distinguish a *useful* extra step from a wasted one.
8. **Prompt changes shift scores:** pre-prompt (0.66) and post-prompt arithmetic results are not comparable.
9. **Non-Groq providers are untested live** (mock tests only), and their default model IDs (`gpt-4o-mini`/`gpt-4o`, `claude-haiku-5-5`/`claude-sonnet-5-5`, `llama3.1`/`qwen2.5`) were not checked against provider docs. Scores across providers are not comparable.
10. **CI has never run on GitHub** (`.github/workflows/ci.yml`; nothing pushed).

---

## Next steps

Priority order:
1. Done 2026-10-22: key, example 01, suite `--node groq`, tool-use prompt, rubric + sampling, judge and `/evaluate` live.
2. Verify the OpenAI/Anthropic/Ollama default model IDs against provider docs and do one live run each (Chapter 8).
3. Replace the AI-written calibration labels with independent human labels (harness exists since Chapter 9).
4. Done 2026-10-24: `judge_samples` exposed in the API.
5. Push and watch the first real CI run; decide whether to drop the unused `sqlalchemy` pin.
6. Optional dollar-cost metric.
7. Persistence of reports (would finally use SQLAlchemy).

---

## Teacher's Notebook

> **Maintained by the `teacher` subagent.** After each user query it adds a dated entry here (newest first) summarising *what was asked, what was answered or changed, and why*, then, if the project changed, updates the relevant chapter above so the story stays true. Entries explain concepts in depth; they are not terse log lines. Older entries below refer to the manual's former "Part N" numbering; the mapping is: Part 8B = Chapter 6, Part 8C = Chapter 7, Part 8 = Chapter 5, Parts 9-13 = the reference sections at the end of this file.

### 2026-10-24 (latest) — Task-list batch: API judge samples, calibration harness, CI
- **Asked:** "do everything possible for now sequentially" on the remaining tasks.
- **Done:** added Chapter 9. `CLAUDE.md` roadmap formatting fixed; `EvaluateRequest.judge_samples` (1-5, 422 outside) with `JudgeFactory` now `temperature -> Judge` (0.7 if samples > 1); new `eval/calibration.py` + `examples/judge_calibration.json` + `tests/test_calibration.py`; new `.github/workflows/ci.yml`. pytest re-run by me: 124 passed (calibration file alone: 14).
- **Why:** sampling a temperature-0 judge repeats one answer, so the API must build the judge hotter. Calibration measures judge vs human marks. CI enforces "no keys needed". Live calibration (MAE 0.100, bias -0.071, agreement 86%, r 0.884) is the caller's report. Caveat: labels were written by the AI author, so this is a smoke test, not real calibration. CI not run on GitHub; `sqlalchemy` pin left for the user; non-Groq providers still untested live; no push. Slip: a multi-file shell command failed to parse, wrote nothing, files recreated with Write.

### 2026-10-24 — Library, not website; swappable LLM providers
- **Asked:** keep AgentEval a Python library (no public website, because of key abuse/quota and upkeep; library users use their own key) and let developers switch LLM APIs while Groq stays the default.
- **Done:** added Chapter 8. New `agent/providers.py` (`Provider`, `PROVIDERS` for groq/openai/anthropic/ollama, `get_provider`, `create_chat_model`); `create_llm_node(model=None, ..., provider=None)`; `create_judge` (with `create_groq_judge` kept as wrapper); CLI `--provider/--model/--judge-provider/--judge-model` and `llm` as the new name for `groq`; API factories turn `RuntimeError` into 503; extras in `pyproject.toml`; `.env.example` and README updated. pytest re-run by me: 107 passed.
- **Why:** a public site would burn the author's free-tier key and need hosting; a library pushes cost and key to the user. A registry plus lazy imports gives choice without forcing every provider package on everyone. Not verified: non-Groq providers live and their default model IDs (mock-tested only). Live Groq CLI re-run (overall 0.68) and the clean missing-key hint for `--provider openai` are the caller's report.

### 2026-10-22 — Manual rewritten as a story
- **Asked:** rewrite `LEARN.md` (712 lines) into the new story format defined in `.claude/agents/teacher.md`: chronological chapters with the five-beat arc, a "Meet the cast" section, and the reference sections kept; keep every technical fact.
- **Done:** converted old Parts 1-8C into a Prologue, an architecture overview, a technology section, and Chapters 1-7 (Parts 4, 5, 6, 7, 8, 8B, 8C respectively). Added "Meet the cast" with the analogy table and where the analogies stop. Kept and re-pointed the file table, "How we test", decision log (now with a Chapter column), limitations, next steps, glossary and this Notebook. Verified the test count with `venv/Scripts/python -m pytest -q`: 95 passed. No code or numbers were changed or invented.
- **Why:** a reader with no AI background should be able to follow what happened and why, while engineers still find the exact names and trade-offs. Cross-references of the form "Part 8B" were rewritten to "Chapter 6" etc.

### 2026-10-22 (later) — Tool-use prompt, judge rubric and sampling, live `/evaluate`
- **Asked:** record three changes verified live on Groq: (1) a system prompt so the model uses tools, (2) judge-bias mitigations (rubric, multi-sample median), (3) `/evaluate` smoke-tested live; explain median vs mean, why temperature 0 makes multi-sampling pointless, and remaining bias risks.
- **Done:** added Part 8C (now Chapter 7) with full explanations; updated Parts 9, 10, 11, glossary. Code: `create_llm_node(..., system_prompt)` + `TOOL_SYSTEM_PROMPT`; `llm_judge(..., samples)`; `create_groq_judge(temperature)`; `Evaluator(judge_samples)`; CLI `--judge-samples`. Tests: 95 pass (I re-ran pytest). Live figures (tool_call_accuracy 0.33 -> 1.0; `/evaluate` overall 0.81, `llm_judge` 1.0, 532 tokens) are the caller's, not re-run by me.
- **Why:** the model answered `2+2` from memory, so the tool metric was measuring prompt under-specification; a nudge fixes it without forcing a tool on every turn. A rubric anchors the judge's scale; the median of N temperature>0 samples damps outliers (the mean would be dragged by them; at temperature 0 all samples are identical). Open: no calibration set, one judge model, criteria vs `expected_output` can disagree, API lacks `judge_samples`, nothing committed yet.

### 2026-10-22 — First live run, retired model, secrets hygiene
- **Asked:** record that `GROQ_API_KEY` is now set (first pasted into `.env.example` by mistake, then moved to `.env`), that Groq retired the default model, and explain `.env.example` and Groq vs Grok vs model publishers.
- **Done:** changed `DEFAULT_MODEL` to `openai/gpt-oss-120b` and `DEFAULT_JUDGE_MODEL` to `qwen/qwen3.8-27b`; live runs reported: example 01 (395 correct), 92 tests, suite CLI (about 0.66 overall, the deliberately wrong `3+3=7` case, and a real finding that `2+2` got `tool_call_accuracy` 0 because the model skipped the tool). Added Part 8B (now Chapter 6) with full explanations; fixed stale llama references in Parts 3, 4.5, 6, 8; updated Parts 9, 10, 11, glossary.
- **Why:** a retired model is a runtime failure that mocked tests cannot catch. A judge from a different family than the agent reduces self-preference bias. Secrets never go in tracked files because the repo is public and git history is permanent. Not yet verified: the judge live, `/evaluate` live.

### 2026-10-17 — Manual created
- **Asked:** a comprehensive manual covering the problem statement, solution, and method for every file and decision from day one, plus a `teacher` agent to keep it current.
- **Done:** wrote Parts 0-13 from the real source and git history (10 commits, 2026-09-30 → 2026-10-17, 92 tests); created `.claude/agents/teacher.md`; added a rule to `CLAUDE.md` to run `teacher` after each query.
- **Why:** the project's decisions were scattered across `CLAUDE.md` (terse), `PROJECT_LOG.md` (diary), and code. This file is the single narrative that connects them.

---

## Glossary

- **Agent** — a program where an LLM repeatedly decides the next action (answer, or call a tool). In the story: the employee.
- **Node** — a function `state -> partial state update` in a LangGraph graph.
- **Edge / conditional edge** — the link deciding which node runs next; conditional edges choose via a function.
- **State** — the shared data (`AgentState`) passed through the graph. In the story: the notebook.
- **Reducer** — a rule for merging a node's returned field into existing state (`add` = append for lists).
- **Superstep** — one round of node execution in LangGraph; `recursion_limit` caps these.
- **Tool / function calling** — the LLM returns a structured request (`name`, `args`) to run a named function instead of text.
- **JSON schema** — a standard way to describe the shape of data; used to tell the LLM a tool's parameters.
- **Mock** — a stand-in object/function used in tests instead of the real dependency. In the story: an understudy.
- **Monkeypatch** — pytest's way to temporarily replace an attribute (e.g., swap `ChatGroq` for a fake).
- **Dependency injection** — passing a dependency in (FastAPI `Depends`) rather than hard-coding it, so tests can substitute it.
- **Fail fast** — raise a clear error as early as possible rather than failing obscurely later.
- **AST** — Abstract Syntax Tree; the parsed structure of code, which we walk safely instead of `eval`-ing.
- **Metric** — a function mapping a run to a 0-1 score, higher = better. In the story: a marking criterion.
- **LLM-as-judge** — using an LLM to grade another LLM's output. In the story: the second examiner.
- **Opt-in** — a feature that does nothing unless explicitly configured.
- **503** — HTTP "Service Unavailable"; used when `GROQ_API_KEY` is missing.
- **`.env.example`** — committed template listing needed variable names with no real values; the real `.env` is git-ignored.
- **Groq vs Grok** — Groq = the inference host we use; Grok = xAI's unrelated model family.
- **Open-weight model** — a model whose trained parameters are published, so any provider (e.g. Groq) can host it; the `openai/` or `qwen/` prefix names the trainer.
- **Self-preference bias** — an LLM judge favouring output resembling its own style; reduced by using a different model family as judge.
- **Subagent** — a specialised Claude Code assistant defined in `.claude/agents/*.md`.
- **System prompt / system message** — a message with role `system` that sets standing instructions for the model; here `TOOL_SYSTEM_PROMPT` nudges tool use.
- **Rubric** — explicit score bands (0-2, 3-5, 6-8, 9-10) given to the judge so its scale is anchored.
- **Median** — the middle value of sorted numbers; unlike the mean, one outlier cannot move it.
- **Temperature** — sampling randomness of an LLM; 0 = (near) deterministic, higher = more varied replies.
- **Multi-sampling** — asking the judge N times and aggregating (`samples` / `--judge-samples`); useful only at temperature > 0.
- **Provider** — a hosted-LLM service (Groq, OpenAI, Anthropic) or a local runner (Ollama), described by a `Provider` entry in `PROVIDERS`. In the story: a staffing agency.
- **Registry** — a lookup table of named options (`PROVIDERS`, also `ToolRegistry`).
- **Lazy import** — importing a package only at the moment it is needed, so unused optional packages need not be installed.
- **Optional extra** — a group of optional dependencies in `pyproject.toml`, installed with `pip install 'agenteval[openai]'`.
- **Ollama** — software that runs open models on your own machine; needs no API key.
- **Calibration set** — human-labelled examples used to check that judge scores agree with human judgement. The harness and a 14-item seed set exist (Chapter 9), but the labels are AI-written, not independent.
- **Mean absolute error (MAE)** — average size of the gap between judge and human scores; lower is better.
- **Bias (judge minus human)** — average signed gap; negative = strict judge, positive = lenient.
- **Pearson correlation (r)** — -1 to 1 measure of whether two score lists rise and fall together.
- **422** — HTTP "Unprocessable": the request body failed validation (e.g. `judge_samples` of 6).
- **CI (continuous integration)** — a robot that re-runs checks on every push; here `.github/workflows/ci.yml`.
- **Smoke test** — a single quick real run proving the pieces connect, not proving correctness.
