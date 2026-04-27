from __future__ import annotations

from collections import defaultdict

KNOWN_METRICS = {"cpu", "mem", "load", "latency", "error"}
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
    service, metric = column_name.rsplit("_", 1)
    if metric.lower() not in KNOWN_METRICS:
        return None
    return service, metric.lower()


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
    for column in columns:
        if column.lower() == target:
            return column
    raise KeyError(f"Metric column not found: {service}_{metric}")
