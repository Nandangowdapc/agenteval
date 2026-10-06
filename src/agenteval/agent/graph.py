"""LangGraph-based agent framework."""

from collections.abc import Callable

from langgraph.graph import StateGraph

from .state import AgentState, create_initial_state


class AgentGraph:
    """Wrapper for LangGraph StateGraph with agent-specific logic."""

    def __init__(self, name: str = "agent"):
        self.name = name
        self.graph = StateGraph(AgentState)
        self._nodes = {}
        # LangGraph's own cap on supersteps per run (its default is 25)
        self.recursion_limit = 25

    def add_node(self, name: str, func: Callable[[AgentState], dict]):
        """Add a node to the graph."""
        self.graph.add_node(name, func)
        self._nodes[name] = func

    def add_edge(self, source: str, target: str):
        """Add an edge between nodes."""
        self.graph.add_edge(source, target)

    def add_conditional_edges(self, source: str, condition: Callable, mapping: dict):
        """Add conditional edges (branching logic)."""
        self.graph.add_conditional_edges(source, condition, mapping)

    def set_entry_point(self, node: str):
        """Set the entry point."""
        self.graph.set_entry_point(node)

    def compile(self):
        """Compile the graph into a runnable."""
        return self.graph.compile()

    def run(self, task: str) -> AgentState:
        """Run the agent on a task."""
        runnable = self.compile()
        initial_state = create_initial_state(task)
        final_state = runnable.invoke(
            initial_state, {"recursion_limit": self.recursion_limit}
        )
        return final_state
