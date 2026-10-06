"""Tool registry and definitions."""

from collections.abc import Callable
from typing import Any


class Tool:
    """Definition of a tool the agent can use."""

    def __init__(
        self,
        name: str,
        func: Callable,
        description: str,
        parameters: dict[str, Any],
    ):
        self.name = name
        self.func = func
        self.description = description
        self.parameters = parameters

    def __call__(self, **kwargs):
        """Execute the tool."""
        return self.func(**kwargs)


class ToolRegistry:
    """Registry of available tools."""

    def __init__(self):
        self._tools = {}

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """List all available tools."""
        return list(self._tools.keys())

    def get_schema(self) -> dict:
        """Get schema of all tools (for LLM)."""
        return {
            name: {
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for name, tool in self._tools.items()
        }


# Example tools
def calculate(expression: str) -> str:
    """Simple calculator."""
    try:
        result = eval(expression)
        return str(result)
    except Exception as e:  # noqa: BLE001 — tools report errors to the LLM, never raise
        return f"Error: {e}"


def search_web(query: str) -> str:
    """Search the web (mock for now)."""
    return f"Mock search results for: {query}"


# Create global registry
tool_registry = ToolRegistry()
tool_registry.register(
    Tool(
        name="calculate",
        func=calculate,
        description="Execute a mathematical expression",
        parameters={
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
    )
)
tool_registry.register(
    Tool(
        name="search",
        func=search_web,
        description="Search the web for information",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )
)
