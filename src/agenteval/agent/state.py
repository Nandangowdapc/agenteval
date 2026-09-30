"""Agent state management for LangGraph workflows."""

from typing import TypedDict, Annotated, Any
from operator import add


class AgentState(TypedDict):
    """
    Immutable agent execution state.
    
    Used in LangGraph StateGraph for tracking agent execution.
    """
    # Conversation history (append-only)
    messages: Annotated[list[dict], add]
    
    # All tool invocations
    tool_calls: Annotated[list[dict], add]
    
    # Tool execution results
    tool_results: Annotated[list[dict], add]
    
    # Current reasoning step
    reasoning: str
    
    # Step counter (for loop detection)
    current_step: int
    
    # Original user task
    task: str
    
    # Performance metrics
    metrics: dict[str, Any]
    
    # Error tracking
    errors: Annotated[list[str], add]


def create_initial_state(task: str) -> AgentState:
    """Create initial agent state for a task."""
    return {
        "messages": [],
        "tool_calls": [],
        "tool_results": [],
        "reasoning": "",
        "current_step": 0,
        "task": task,
        "metrics": {},
        "errors": [],
    }
