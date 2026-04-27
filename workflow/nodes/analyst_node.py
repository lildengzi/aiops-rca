from __future__ import annotations

from agents.analyst_agent import AnalystAgent
from workflow.graph_state import GraphState
from workflow.state import RCAState
from workflow.utils import record_node_event


def analyst_node(state: RCAState, agent: AnalystAgent) -> dict:
    result = agent.run(state)
    state.final_result = result
    state.decisions.append(result)
    return record_node_event(state, agent.name, result)


def analyst_graph_node(graph_state: GraphState, agent: AnalystAgent) -> GraphState:
    state = RCAState.from_graph_state(graph_state)
    result = analyst_node(state, agent)
    return {
        "final_result": result,
        "decisions": state.decisions,
        "knowledge_hits": state.knowledge_hits,
        "llm_enabled": state.llm_enabled,
        "llm_reason": state.llm_reason,
        "think_log_path": state.think_log_path,
        "node_history": state.node_history[-1:],
    }
