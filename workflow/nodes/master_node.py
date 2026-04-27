from __future__ import annotations

from agents.master_agent import MasterAgent
from workflow.graph_state import GraphState
from workflow.state import RCAState
from workflow.utils import record_node_event


def master_node(state: RCAState, agent: MasterAgent) -> dict:
    result = agent.run(state)
    state.plan = result
    return record_node_event(state, agent.name, result)


def master_graph_node(graph_state: GraphState, agent: MasterAgent) -> GraphState:
    state = RCAState.from_graph_state(graph_state)
    state.iteration += 1
    result = master_node(state, agent)
    return {
        "iteration": state.iteration,
        "plan": result,
        "knowledge_hits": state.knowledge_hits,
        "llm_enabled": state.llm_enabled,
        "llm_reason": state.llm_reason,
        "think_log_path": state.think_log_path,
        "node_history": state.node_history[-1:],
    }
