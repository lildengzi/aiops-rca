from __future__ import annotations

from workflow.graph_state import GraphState
from workflow.state import RCAState
from workflow.utils import record_node_event


KEYWORDS = {
    "latency": ["延迟", "慢", "latency"],
    "cpu": ["cpu", "负载", "load"],
    "memory": ["内存", "mem", "memory"],
    "error": ["错误", "error", "异常"],
}


def detect_fault_node(state: RCAState) -> dict[str, list[str]]:
    lowered = state.user_input.lower()
    matched = []
    for fault_type, candidates in KEYWORDS.items():
        if any(token in lowered for token in candidates):
            matched.append(fault_type)
    result = {"fault_types": matched or ["unknown"]}
    state.detected_fault = result
    return record_node_event(state, "detect_fault", result)


def detect_fault_graph_node(graph_state: GraphState) -> GraphState:
    state = RCAState.from_graph_state(graph_state)
    result = detect_fault_node(state)
    return {
        "detected_fault": result,
        "think_log_path": state.think_log_path,
        "node_history": state.node_history[-1:],
    }
