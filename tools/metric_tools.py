from __future__ import annotations

from typing import Any

from utils.anomaly_detection import detect_anomaly_zscore, summarize_series
from utils.data_loader import CSVDataLoader
from utils.service_parser import find_metric_column


class MetricToolbox:
    def __init__(self, loader: CSVDataLoader):
        self.loader = loader

    def query_service_metrics(
        self,
        service: str,
        metric: str,
        start: int | None = None,
        end: int | None = None,
    ) -> list[dict[str, Any]]:
        frame = self.loader.filter_by_time(start=start, end=end)
        timestamp_column = self.loader.timestamp_column
        metric_column = find_metric_column(frame.columns.tolist(), service, metric)
        subset = frame[[timestamp_column, metric_column]].copy()
        subset.columns = ["timestamp", "value"]
        return subset.to_dict(orient="records")

    def summarize_metric(
        self,
        service: str,
        metric: str,
        start: int | None = None,
        end: int | None = None,
        threshold: float = 2.5,
    ) -> dict[str, Any]:
        frame = self.loader.filter_by_time(start=start, end=end)
        timestamp_column = self.loader.timestamp_column
        metric_column = find_metric_column(frame.columns.tolist(), service, metric)
        series = frame[metric_column]
        anomaly_indices = detect_anomaly_zscore(series, threshold=threshold)
        timestamps = frame.iloc[anomaly_indices][timestamp_column].tolist() if anomaly_indices else []
        stats = summarize_series(series)
        return {
            "service": service,
            "metric": metric,
            "stats": stats,
            "is_anomalous": bool(anomaly_indices),
            "anomaly_indices": anomaly_indices,
            "anomaly_timestamps": [int(value) for value in timestamps],
            "peak_value": stats["max"],
        }
