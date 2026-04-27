from __future__ import annotations

from agents.reporter_agent import ReporterAgent
from workflow.graph_state import GraphState
from workflow.state import RCAState
from workflow.utils import record_node_event


def reporter_node(state: RCAState, agent: ReporterAgent) -> dict:
    result = agent.run(state)
    state.report_path = result.get("report_path")
    state.report_header = result.get("report_header") or {}
    return record_node_event(state, agent.name, result)


def reporter_graph_node(graph_state: GraphState, agent: ReporterAgent) -> GraphState:
    state = RCAState.from_graph_state(graph_state)
    result = reporter_node(state, agent)
    return {
        "report_path": result.get("report_path"),
        "report_header": state.report_header,
        "think_log_path": state.think_log_path,
        "node_history": state.node_history[-1:],
    }
