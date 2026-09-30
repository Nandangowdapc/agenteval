# AgentEval

Production evaluation framework for agentic AI systems, built on LangGraph.

## Layout

```
src/agenteval/
├── __init__.py
└── agent/
    ├── state.py   # AgentState TypedDict + initial-state factory
    ├── graph.py   # AgentGraph wrapper around LangGraph's StateGraph
    ├── tools.py   # Tool registry (calculate, search, ...)
    └── llm.py     # Groq-backed LLM inference node
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

## Run

```bash
python examples/01_simple_agent.py
pytest tests/ -v
```
