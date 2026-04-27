from __future__ import annotations

from workflow.graph_state import GraphState
from workflow.state import RCAState
from workflow.utils import record_node_event


def aggregate_node(
    state: RCAState,
    metric_output: dict,
    log_output: dict,
    trace_output: dict,
) -> dict:
    result = {
        "metrics": metric_output.get("metrics", []),
        "logs": log_output.get("logs", []),
        "traces": trace_output.get("traces", []),
    }
    state.evidence = result
    record_node_event(
        state,
        "aggregate",
        {
            "metric_count": len(result["metrics"]),
            "log_count": len(result["logs"]),
            "trace_count": len(result["traces"]),
        },
    )
    return result


def aggregate_graph_node(graph_state: GraphState) -> GraphState:
    state = RCAState.from_graph_state(graph_state)
    result = {
        "metrics": list(state.evidence.get("metrics", [])),
        "logs": list(state.evidence.get("logs", [])),
        "traces": list(state.evidence.get("traces", [])),
    }
    state.evidence = result
    record_node_event(
        state,
        "aggregate",
        {
            "metric_count": len(result["metrics"]),
            "log_count": len(result["logs"]),
            "trace_count": len(result["traces"]),
        },
    )
    return {
        "evidence": result,
        "think_log_path": state.think_log_path,
        "node_history": state.node_history[-1:],
    }
