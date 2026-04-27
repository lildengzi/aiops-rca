from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from workflow.builder import WorkflowRuntime

from workflow.graph_state import GraphState
from workflow.query_builders import build_knowledge_query
from workflow.state import RCAState
from workflow.utils import record_node_event


def retrieve_knowledge_graph_node(graph_state: GraphState, runtime: "WorkflowRuntime") -> GraphState:
    state = RCAState.from_graph_state(graph_state)
    query_payload = build_knowledge_query(state)
    knowledge_hits = []
    retrieval_status = "retriever unavailable"

    if runtime.knowledge_retriever:
        try:
            knowledge_hits = runtime.knowledge_retriever.retrieve_for_context(query_payload)
            retrieval_status = "ok"
        except Exception as exc:
            retrieval_status = str(exc)

    state.knowledge_hits = knowledge_hits
    service_distribution: dict[str, int] = {}
    for hit in knowledge_hits:
        service = str(hit.get("service") or "unknown")
        service_distribution[service] = service_distribution.get(service, 0) + 1

    record_node_event(
        state,
        "retrieve_knowledge",
        {
            "global_query": query_payload.get("global_query"),
            "service_queries": query_payload.get("service_queries", []),
            "candidate_services": query_payload.get("candidate_services", []),
            "candidate_metrics": query_payload.get("candidate_metrics", []),
            "hit_count": len(knowledge_hits),
            "service_distribution": service_distribution,
            "top_hits": [
                {
                    "title": item.get("title"),
                    "service": item.get("service"),
                    "fault_type": item.get("fault_type"),
                    "score": item.get("score"),
                    "retrieval_stage": item.get("retrieval_stage"),
                    "match_reasons": item.get("match_reasons", []),
                }
                for item in knowledge_hits[:5]
            ],
            "status": retrieval_status,
        },
    )
    return {
        "knowledge_hits": knowledge_hits,
        "think_log_path": state.think_log_path,
        "node_history": state.node_history[-1:],
    }
