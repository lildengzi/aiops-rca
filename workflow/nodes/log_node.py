from __future__ import annotations

from agents.log_agent import LogAgent
from workflow.graph_state import GraphState
from workflow.state import RCAState
from workflow.utils import record_node_event


def log_node(state: RCAState, agent: LogAgent) -> dict:
    result = agent.run(state)
    return record_node_event(state, agent.name, result)


def log_graph_node(graph_state: GraphState, agent: LogAgent) -> GraphState:
    state = RCAState.from_graph_state(graph_state)
    result = log_node(state, agent)
    return {
        "evidence": {
            "logs": result.get("logs", []),
        },
        "think_log_path": state.think_log_path,
        "node_history": state.node_history[-1:],
    }
