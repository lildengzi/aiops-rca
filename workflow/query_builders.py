from __future__ import annotations

from typing import Any

from workflow.state import RCAState


FOCUS_METRICS = ["error", "latency", "cpu", "mem", "load"]


def _normalize_fault_type(fault_type: str) -> str:
    return "mem" if fault_type == "memory" else fault_type


def _candidate_services(state: RCAState, limit: int = 5) -> list[str]:
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
    window_start = state.dataset_summary.get("window_start")
    window_end = state.dataset_summary.get("window_end")

    global_lines = [state.user_input]
    if fault_types:
        global_lines.append(f"Fault types: {', '.join(fault_types)}")
    if candidate_services:
        global_lines.append(f"Candidate services: {', '.join(candidate_services)}")
    if candidate_metrics:
        global_lines.append(f"Candidate metrics: {', '.join(candidate_metrics)}")
    if window_start is not None or window_end is not None:
        global_lines.append(f"Window: {window_start} - {window_end}")

    service_queries = []
    for service in candidate_services:
        query_lines = [
            state.user_input,
            f"Service: {service}",
        ]
        if fault_types:
            query_lines.append(f"Fault types: {', '.join(fault_types)}")
        if candidate_metrics:
            query_lines.append(f"Metrics: {', '.join(candidate_metrics[:3])}")
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
        "time_window": {
            "start": window_start,
            "end": window_end,
        },
    }
