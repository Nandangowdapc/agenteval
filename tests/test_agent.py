"""Tests for agent framework."""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from src.agenteval.agent.state import AgentState, create_initial_state
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
        "messages", "tool_calls", "tool_results", 
        "reasoning", "current_step", "task", "metrics", "errors"
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
