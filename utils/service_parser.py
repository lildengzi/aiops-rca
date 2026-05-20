from __future__ import annotations

from collections import defaultdict

KNOWN_METRICS = {
    "cpu",
    "mem",
    "memory",
    "load",
    "latency",
    "error",
    "socket",
    "disk",
    "network",
    "drop",
    "throughput",
    "status",
}
IGNORED_PREFIXES = {"time", "timestamp"}


def normalize_timestamp_column(columns: list[str]) -> str:
    for name in columns:
        lowered = name.lower()
        if lowered in {"time", "timestamp"}:
            return name
    raise ValueError("No timestamp column found in CSV data.")


def split_service_metric(column_name: str) -> tuple[str, str] | None:
    lowered = column_name.lower()
    if lowered in IGNORED_PREFIXES:
        return None
    if "_" not in column_name:
        return None
    service, raw_metric = column_name.split("_", 1)
    metric = normalize_metric_name(raw_metric)
    if metric not in KNOWN_METRICS:
        return None
    if metric == "memory":
        metric = "mem"
    return service, metric


def normalize_metric_name(value: str) -> str:
    lowered = value.lower().replace("_", "-")
    if "latency" in lowered:
        return "latency"
    if "status" in lowered or "http" in lowered:
        return "status"
    if "error" in lowered or "errs" in lowered or "failures" in lowered:
        return "error"
    if "drop" in lowered or "dropped" in lowered:
        return "drop"
    if "network" in lowered or "receive" in lowered or "transmit" in lowered:
        if "bytes" in lowered or "packets" in lowered:
            return "throughput"
        return "network"
    if "memory" in lowered or lowered.startswith("mem"):
        return "memory"
    if "cpu" in lowered:
        return "cpu"
    if "load" in lowered or "request-total" in lowered:
        return "load"
    if "socket" in lowered:
        return "socket"
    if "disk" in lowered or "blkio" in lowered or "fs-" in lowered:
        return "disk"
    return lowered


def discover_services(columns: list[str]) -> list[str]:
    services = set()
    for column in columns:
        parsed = split_service_metric(column)
        if parsed:
            services.add(parsed[0])
    return sorted(services)


def discover_service_metrics(columns: list[str]) -> dict[str, list[str]]:
    service_metrics: dict[str, list[str]] = defaultdict(list)
    for column in columns:
        parsed = split_service_metric(column)
        if parsed:
            service, metric = parsed
            service_metrics[service].append(metric)
    return {service: sorted(set(metrics)) for service, metrics in service_metrics.items()}


def find_metric_column(columns: list[str], service: str, metric: str) -> str:
    target = f"{service}_{metric}".lower()
    normalized_metric = "memory" if metric == "mem" else metric
    for column in columns:
        if column.lower() == target:
            return column
        parsed = split_service_metric(column)
        if parsed and parsed[0].lower() == service.lower() and parsed[1] == normalized_metric:
            return column
    raise KeyError(f"Metric column not found: {service}_{metric}")
