"""Tool registry and definitions."""

import ast
import operator
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
class _CalcError(Exception):
    """Raised for expressions the safe calculator refuses to evaluate."""


_BINARY_OPS: dict[type, Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS: dict[type, Callable[[Any], Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_MAX_EXPONENT = 100
_MAX_POW_BITS = 10_000  # caps int results of chained powers like ((9**100)**100)**100


def _eval_node(node: ast.AST) -> int | float:
    """Recursively evaluate an AST node, allowing only arithmetic on numbers."""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise _CalcError("only numeric constants are allowed")
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Pow):
            if abs(right) > _MAX_EXPONENT:
                raise _CalcError(f"exponent too large (max {_MAX_EXPONENT})")
            if (
                isinstance(left, int)
                and isinstance(right, int)
                and left.bit_length() * abs(right) > _MAX_POW_BITS
            ):
                raise _CalcError("result of ** is too large")
        return _BINARY_OPS[type(node.op)](left, right)
    raise _CalcError(f"unsupported expression element: {type(node).__name__}")


def calculate(expression: str) -> str:
    """Safely evaluate an arithmetic expression (numbers, + - * / // % **, parentheses)."""
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        return str(_eval_node(tree))
    except ZeroDivisionError:
        return "Error: division by zero"
    except SyntaxError as e:
        return f"Error: invalid expression ({e.msg})"
    except OverflowError:
        return "Error: result too large"
    except (ValueError, _CalcError) as e:
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
        description="Evaluate an arithmetic expression. Arithmetic only: no variables, functions or code.",
        parameters={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Arithmetic expression using numbers, + - * / // % ** and parentheses, e.g. '(3 + 4) * 2'",
                }
            },
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
