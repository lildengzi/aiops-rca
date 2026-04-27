from __future__ import annotations

from agents.metric_agent import MetricAgent
from workflow.graph_state import GraphState
from workflow.state import RCAState
from workflow.utils import record_node_event


def metric_node(state: RCAState, agent: MetricAgent) -> dict:
    result = agent.run(state)
    return record_node_event(state, agent.name, result)


def metric_graph_node(graph_state: GraphState, agent: MetricAgent) -> GraphState:
    state = RCAState.from_graph_state(graph_state)
    result = metric_node(state, agent)
    return {
        "evidence": {
            "metrics": result.get("metrics", []),
        },
        "think_log_path": state.think_log_path,
        "node_history": state.node_history[-1:],
    }
