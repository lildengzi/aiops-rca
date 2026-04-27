from __future__ import annotations

from agents.trace_agent import TraceAgent
from workflow.graph_state import GraphState
from workflow.state import RCAState
from workflow.utils import record_node_event


def trace_node(state: RCAState, agent: TraceAgent) -> dict:
    result = agent.run(state)
    return record_node_event(state, agent.name, result)


def trace_graph_node(graph_state: GraphState, agent: TraceAgent) -> GraphState:
    state = RCAState.from_graph_state(graph_state)
    result = trace_node(state, agent)
    return {
        "evidence": {
            "traces": result.get("traces", []),
        },
        "think_log_path": state.think_log_path,
        "node_history": state.node_history[-1:],
    }
