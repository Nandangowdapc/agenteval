"""Simple agent example."""

import os
import sys

# Windows consoles default to a codepage that can't print the emoji below
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langgraph.graph import END

from src.agenteval.agent.graph import AgentGraph
from src.agenteval.agent.llm import create_llm_node
from src.agenteval.agent.state import create_initial_state
from src.agenteval.agent.tools import tool_registry


def simple_agent_example():
    """Run a simple agent example."""

    print("=" * 60)
    print("AgentEval - Simple Agent Example")
    print("=" * 60)

    # Create initial state
    task = "What is 2 + 2?"
    state = create_initial_state(task)

    print(f"\n📝 Task: {state['task']}")
    print(f"📊 Initial state keys: {list(state.keys())}")
    print(f"📍 Current step: {state['current_step']}")

    # Show available tools
    print("\n🔧 Available tools:")
    for tool_name in tool_registry.list_tools():
        tool = tool_registry.get(tool_name)
        print(f"   - {tool_name}: {tool.description}")

    # Execute a tool
    print("\n⚙️  Executing tool: calculate")
    calc_tool = tool_registry.get("calculate")
    result = calc_tool(expression="2 + 2")
    print(f"   Result: {result}")

    # Show full tool schema
    print("\n📋 Tool Schema:")
    schema = tool_registry.get_schema()
    for tool_name, tool_schema in schema.items():
        print(f"   {tool_name}:")
        print(f"      Description: {tool_schema['description']}")
        print(f"      Parameters: {tool_schema['parameters']}")

    print("\n✅ Agent framework is working!")
    print("=" * 60)

    # Run a single LLM reasoning step through the graph (needs GROQ_API_KEY)
    print("\n🧠 Running LLM node via AgentGraph...")
    if not os.environ.get("GROQ_API_KEY"):
        print("   ⚠️  GROQ_API_KEY not set — skipping live LLM call.")
        print(
            "   Copy .env.example to .env and add a free key from https://console.groq.com/keys"
        )
    else:
        graph = AgentGraph(name="simple-agent")
        graph.add_node("llm", create_llm_node())
        graph.set_entry_point("llm")
        graph.add_edge("llm", END)
        final_state = graph.run(task)
        print(f"   Response: {final_state['messages'][-1]['content']}")

    print("=" * 60)


if __name__ == "__main__":
    simple_agent_example()
