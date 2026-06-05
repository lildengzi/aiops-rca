from __future__ import annotations

from typing import Any

import pandas as pd

from benchmark_case_loader import case_context_for_path
from utils.global_anomaly import scan_global_metric_anomalies
from utils.log_template_anomaly import scan_log_template_anomalies
from utils.data_loader import CSVDataLoader


def build_dataset_summary(loader: CSVDataLoader, start: int | None = None, end: int | None = None) -> dict[str, Any]:
    metadata = loader.get_metadata()
    data_path = metadata.get("data_path") or metadata.get("csv_path")
    case_context = case_context_for_path(data_path) if data_path else {}
    window = loader.filter_by_time(start=start, end=end)
    timestamp_column = loader.timestamp_column
    service_graph = _build_service_graph(metadata.get("services", []))
    global_anomalies = scan_global_metric_anomalies(
        loader.load_metrics(),
        start=start,
        end=end,
        service_metrics=metadata.get("service_metrics", {}),
    )
    log_template_anomalies = scan_log_template_anomalies(
        loader.load_log_templates(),
        start=start,
        end=end,
    )
    return {
        **metadata,
        "dataset_kind": metadata.get("dataset_kind", "file"),
        "data_path": data_path,
        "csv_path": data_path,
        "case_context": case_context,
        "dataset": case_context.get("dataset"),
        "scenario": case_context.get("scenario"),
        "case_id": case_context.get("case_id"),
        "window_rows": int(len(window)),
        "window_start": int(window[timestamp_column].min()) if not window.empty else None,
        "window_end": int(window[timestamp_column].max()) if not window.empty else None,
        "has_logs": metadata.get("log_rows", 0) > 0,
        "has_traces": metadata.get("trace_rows", 0) > 0,
        "inject_time": metadata.get("inject_time"),
        "service_graph": service_graph,
        "global_metric_anomalies": global_anomalies,
        "global_anomaly_services": [item["service"] for item in global_anomalies],
        "log_template_anomalies": log_template_anomalies,
        "log_template_anomaly_services": [item["service"] for item in log_template_anomalies],
        "entry_services": [
            service
            for service, details in service_graph.items()
            if details.get("type") == "web" and service in metadata.get("services", [])
        ],
        "observability_summary": {
            "metrics": {
                "available": True,
                "rows": int(len(window)),
                "service_count": metadata.get("service_count", len(metadata.get("services", []))),
                "metric_column_count": metadata.get("metric_column_count", 0),
            },
            "logs": {
                "available": metadata.get("log_rows", 0) > 0,
                "rows": metadata.get("log_rows", 0),
                "template_rows": metadata.get("log_template_rows", 0),
            },
            "traces": {
                "available": metadata.get("trace_rows", 0) > 0,
                "rows": metadata.get("trace_rows", 0),
            },
        },
    }


def frame_to_records(frame: pd.DataFrame, limit: int = 20) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    return frame.head(limit).to_dict(orient="records")


def _build_service_graph(services: list[str]) -> dict[str, dict[str, Any]]:
    # Local import avoids a module cycle: topology_tools imports CSVDataLoader.
    from tools.topology_tools import SERVICE_TOPOLOGY

    service_set = {str(service) for service in services}
    graph: dict[str, dict[str, Any]] = {}
    for service in service_set:
        details = SERVICE_TOPOLOGY.get(service, {})
        downstreams = [item for item in details.get("dependencies", []) if item in service_set]
        graph[service] = {
            "type": details.get("type", "application"),
            "downstreams": downstreams,
            "upstreams": [],
        }
    for source, details in graph.items():
        for target in details["downstreams"]:
            graph.setdefault(target, {"type": "application", "downstreams": [], "upstreams": []})
            graph[target]["upstreams"].append(source)
    for details in graph.values():
        details["upstreams"] = sorted(set(details["upstreams"]))
        details["downstreams"] = sorted(set(details["downstreams"]))
    return graph
