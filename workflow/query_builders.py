from __future__ import annotations

from typing import Any

from workflow.state import RCAState


FOCUS_METRICS = ["error", "latency", "cpu", "mem", "load"]


def _normalize_fault_type(fault_type: str) -> str:
    return "mem" if fault_type == "memory" else fault_type


def _candidate_services(state: RCAState, limit: int = 5) -> list[str]:
    global_services = [
        str(service)
        for service in state.dataset_summary.get("global_anomaly_services", [])
        if str(service).strip()
    ]
    if global_services:
        return global_services[:limit]
    service_metrics = state.dataset_summary.get("service_metrics", {})
    fault_types = {
        _normalize_fault_type(str(item)) for item in state.detected_fault.get("fault_types", []) if str(item).strip()
    }
    scored: list[tuple[str, int]] = []
    for service, metrics in service_metrics.items():
        metric_list = [str(metric) for metric in metrics]
        score = 0
        for fault_type in fault_types:
            if fault_type in metric_list:
                score += 2
        for metric in FOCUS_METRICS:
            if metric in metric_list:
                score += 1
        scored.append((service, score))
    scored.sort(key=lambda item: (-item[1], item[0]))
    return [service for service, _ in scored[:limit]]


def _candidate_metrics(state: RCAState) -> list[str]:
    fault_types = [
        _normalize_fault_type(str(item))
        for item in state.detected_fault.get("fault_types", [])
        if str(item).strip() and str(item) != "unknown"
    ]
    metrics = []
    for metric in fault_types + FOCUS_METRICS:
        if metric not in metrics:
            metrics.append(metric)
    return metrics


def build_knowledge_query(state: RCAState) -> dict[str, Any]:
    fault_types = [str(item) for item in state.detected_fault.get("fault_types", []) if str(item).strip()]
    candidate_services = _candidate_services(state)
    candidate_metrics = _candidate_metrics(state)
    service_graph = state.dataset_summary.get("service_graph", {})
    entry_services = state.dataset_summary.get("entry_services", [])
    observability_summary = state.dataset_summary.get("observability_summary", {})
    window_start = state.dataset_summary.get("window_start")
    window_end = state.dataset_summary.get("window_end")
    chain_lines = _build_chain_lines(candidate_services, service_graph)

    global_lines = [state.user_input]
    if fault_types:
        global_lines.append(f"Fault types: {', '.join(fault_types)}")
    if candidate_services:
        global_lines.append(f"Candidate services: {', '.join(candidate_services)}")
    if entry_services:
        global_lines.append(f"Entry services: {', '.join(entry_services)}")
    if chain_lines:
        global_lines.append("Service chain context:")
        global_lines.extend(chain_lines)
    if candidate_metrics:
        global_lines.append(f"Evidence metric dimensions: {', '.join(candidate_metrics)}")
    if observability_summary:
        global_lines.append(f"Observability pillars: {observability_summary}")
    if window_start is not None or window_end is not None:
        global_lines.append(f"Window: {window_start} - {window_end}")

    service_queries = []
    for service in candidate_services:
        query_lines = [
            state.user_input,
            f"Service: {service}",
        ]
        graph_details = service_graph.get(service, {})
        upstreams = graph_details.get("upstreams", [])
        downstreams = graph_details.get("downstreams", [])
        if upstreams:
            query_lines.append(f"Upstream services: {', '.join(upstreams)}")
        if downstreams:
            query_lines.append(f"Downstream services: {', '.join(downstreams)}")
        if fault_types:
            query_lines.append(f"Fault types: {', '.join(fault_types)}")
        if candidate_metrics:
            query_lines.append(f"Evidence metrics: {', '.join(candidate_metrics[:3])}")
        service_queries.append(
            {
                "service": service,
                "query": "\n".join(query_lines),
            }
        )

    return {
        "global_query": "\n".join(global_lines),
        "service_queries": service_queries,
        "fault_types": fault_types,
        "candidate_services": candidate_services,
        "candidate_metrics": candidate_metrics,
        "service_graph": service_graph,
        "entry_services": entry_services,
        "observability_summary": observability_summary,
        "chain_context": chain_lines,
        "time_window": {
            "start": window_start,
            "end": window_end,
        },
    }


def _build_chain_lines(candidate_services: list[str], service_graph: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for service in candidate_services:
        details = service_graph.get(service, {})
        upstreams = details.get("upstreams", [])
        downstreams = details.get("downstreams", [])
        relation_parts = []
        if upstreams:
            relation_parts.append(f"upstream={','.join(upstreams)}")
        if downstreams:
            relation_parts.append(f"downstream={','.join(downstreams)}")
        if relation_parts:
            lines.append(f"- {service}: {'; '.join(relation_parts)}")
    return lines
