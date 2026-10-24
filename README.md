# AgentEval

Production evaluation framework for agentic AI systems, built on LangGraph.

## Layout

```
src/agenteval/
├── __init__.py
├── agent/
│   ├── state.py   # AgentState TypedDict + initial-state factory
│   ├── graph.py   # AgentGraph wrapper around LangGraph's StateGraph
│   ├── tools.py   # Tool registry (calculate, search, ...)
│   └── llm.py     # LLM inference node (Groq default, pluggable providers)
└── eval/
    ├── metrics.py    # Scoring functions (exact_match, tool_call_accuracy, ...)
    └── evaluator.py  # EvalCase / Evaluator / EvalReport
tests/          # pytest suite
examples/       # runnable examples
```

## Setup

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
copy .env.example .env         # Windows; cp on macOS/Linux
```

Add a free Groq API key to `.env` (get one at https://console.groq.com/keys):

```
GROQ_API_KEY=your-key-here
```

### Other LLM providers

Groq is the default. To use another, install its extra, add its key to `.env`, and
pick it with `AGENTEVAL_PROVIDER=<name>`, `--provider <name>` on the CLI, or
`create_llm_node(provider="<name>")` / `create_judge("<name>")` in code.

| Provider | Install | Key | Default agent / judge model |
|---|---|---|---|
| `groq` (default) | included | `GROQ_API_KEY` | `openai/gpt-oss-120b` / `qwen/qwen3.8-27b` |
| `openai` | `pip install -e ".[openai]"` | `OPENAI_API_KEY` | `gpt-4o-mini` / `gpt-4o` |
| `anthropic` | `pip install -e ".[anthropic]"` | `ANTHROPIC_API_KEY` | `claude-haiku-5-5` / `claude-sonnet-5-5` |
| `ollama` | `pip install -e ".[ollama]"` | none (local server) | `llama3.1` / `qwen2.5` |

Override models with `--model` / `--judge-model` (the judge can use a different
provider via `--judge-provider`). Only Groq has been run live; the others are
covered by mocked tests. Tool-calling quality varies, especially for small local
models. Defaults live in `agent/providers.py`.

## Run

```bash
python examples/01_simple_agent.py
python examples/02_evaluate_agent.py
pytest tests/ -v
```

## Evaluation

`agenteval.eval` scores agent runs against a suite of `EvalCase`s:

```python
from langgraph.graph import END
from agenteval import AgentGraph, EvalCase, Evaluator

graph = AgentGraph(name="my-agent")
graph.add_node("llm", create_llm_node())  # or any node function
graph.set_entry_point("llm")
graph.add_edge("llm", END)

cases = [
    EvalCase(task="What is 2 + 2?", expected_output="4", expected_tools=["calculate"]),
]

report = Evaluator(graph).evaluate(cases)
print(report.summary())  # {"exact_match": 1.0, ..., "overall": 1.0}
```

Built-in metrics (`agenteval.eval.metrics`), each scored 0–1 (higher is better):

- `exact_match` / `contains_match` — compare the final message to an expected output
- `tool_call_accuracy` — fraction of expected tools actually called
- `step_efficiency` — rewards reaching an answer in fewer steps
- `success_rate` — 1.0 if the run recorded no errors
- `llm_judge` (`agenteval.eval.judge`) — an LLM grades the final answer against free-text `EvalCase.judge_criteria` (0–10, normalised to 0–1). Opt in with `Evaluator(graph, judge=create_groq_judge())`; suite files take `judge_criteria`, the CLI takes `--judge groq`, and `POST /evaluate` accepts `judge_criteria` per case (needs `GROQ_API_KEY`). Without a judge or criteria the score is simply omitted.
