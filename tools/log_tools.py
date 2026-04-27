from __future__ import annotations

from typing import Any

from utils.anomaly_detection import detect_anomaly_zscore
from utils.data_loader import CSVDataLoader
from utils.service_parser import find_metric_column


class LogToolbox:
    def __init__(self, loader: CSVDataLoader):
        self.loader = loader

    def query_service_logs(
        self,
        service: str,
        start: int | None = None,
        end: int | None = None,
    ) -> list[dict[str, Any]]:
        frame = self.loader.filter_by_time(start=start, end=end)
        columns = frame.columns.tolist()
        timestamp_column = self.loader.timestamp_column
        logs: list[dict[str, Any]] = []

        rules = [
            ("cpu", 80.0, "ERROR", "CPU saturation detected"),
            ("mem", 9e7, "WARN", "Memory usage remains elevated"),
            ("load", 300.0, "ERROR", "Request load spike detected"),
            ("latency", 0.05, "ERROR", "Service latency spike detected"),
            ("error", 1.0, "ERROR", "Application error count increased"),
        ]

        for metric, absolute_threshold, level, template in rules:
            try:
                metric_column = find_metric_column(columns, service, metric)
            except KeyError:
                continue
            series = frame[metric_column]
            anomaly_indices = set(detect_anomaly_zscore(series, threshold=2.5))
            for index, row in frame.iterrows():
                value = float(row[metric_column])
                if value >= absolute_threshold or index in anomaly_indices:
                    logs.append(
                        {
                            "timestamp": int(row[timestamp_column]),
                            "service": service,
                            "level": level,
                            "message": f"{template}: {metric}={value:.6f}",
                            "metric": metric,
                            "value": value,
                        }
                    )

        return sorted(logs, key=lambda item: item["timestamp"])

    def summarize_logs(
        self,
        service: str,
        start: int | None = None,
        end: int | None = None,
    ) -> dict[str, Any]:
        logs = self.query_service_logs(service=service, start=start, end=end)
        patterns: dict[str, int] = {}
        for log in logs:
            key = f"{log['level']}::{log['metric']}"
            patterns[key] = patterns.get(key, 0) + 1
        top_patterns = sorted(patterns.items(), key=lambda item: item[1], reverse=True)
        return {
            "service": service,
            "log_count": len(logs),
            "top_patterns": [{"pattern": key, "count": count} for key, count in top_patterns[:5]],
            "sample_logs": logs[:10],
        }
