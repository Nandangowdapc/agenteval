"""Tests for agent framework."""

import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from src.agenteval.agent.state import create_initial_state
from src.agenteval.agent.tools import tool_registry


def test_create_initial_state():
    """Test initial state creation."""
    state = create_initial_state("test task")

    assert state["task"] == "test task"
    assert state["current_step"] == 0
    assert state["messages"] == []
    assert state["tool_calls"] == []


def test_initial_state_keys():
    """Test that initial state has all required keys."""
    state = create_initial_state("sample task")

    required_keys = {
        "messages",
        "tool_calls",
        "tool_results",
        "reasoning",
        "current_step",
        "task",
        "metrics",
        "errors",
    }
    assert required_keys.issubset(set(state.keys()))


def test_tool_registry_get():
    """Test tool registration and retrieval."""
    calc_tool = tool_registry.get("calculate")

    assert calc_tool is not None
    assert calc_tool.name == "calculate"


def test_tool_execution():
    """Test executing a tool."""
    calc_tool = tool_registry.get("calculate")
    result = calc_tool(expression="2 + 2")

    assert result == "4"


def test_tool_list():
    """Test listing all tools."""
    tools = tool_registry.list_tools()

    assert "calculate" in tools
    assert "search" in tools
    assert len(tools) >= 2


def test_tool_schema():
    """Test getting tool schema."""
    schema = tool_registry.get_schema()

    assert "calculate" in schema
    assert "search" in schema
    assert "description" in schema["calculate"]
    assert "parameters" in schema["calculate"]


@pytest.mark.parametrize(
    "expression, expected",
    [
        ("2 + 2", "4"),
        ("10 / 4", "2.5"),
        ("7 // 2", "3"),
        ("7 % 3", "1"),
        ("2 ** 10", "1024"),
        ("-3 + +5", "2"),
        ("2 + 3 * 4", "14"),
        ("(2 + 3) * 4", "20"),
        ("(3 + 4) * 2", "14"),
        ("2 ** 3 ** 2", "512"),
    ],
)
def test_calculate_arithmetic(expression, expected):
    """Normal arithmetic, precedence and parentheses."""
    assert tool_registry.get("calculate")(expression=expression) == expected


@pytest.mark.parametrize(
    "expression",
    [
        "1 / 0",
        "1 // 0",
        "5 % 0",
        "__import__('os').system('echo hi')",
        "__import__('os')",
        "x + 1",
        "'a' + 'b'",
        "True + 1",
        "(1).real",
        "[1, 2][0]",
        "9 ** 9 ** 9",
        "2 ** 101",
        "((9 ** 100) ** 100) ** 100",
        "2 +",
        "",
    ],
)
def test_calculate_rejects_bad_input(expression):
    """Unsafe, unsupported or invalid input returns an Error string, never raises."""
    result = tool_registry.get("calculate")(expression=expression)
    assert result.startswith("Error:")


def test_calculate_schema_describes_expression():
    """The expression parameter is documented for the LLM."""
    schema = tool_registry.get_schema()["calculate"]
    assert "arithmetic" in schema["description"].lower()
    assert schema["parameters"]["properties"]["expression"]["description"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
