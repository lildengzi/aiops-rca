from __future__ import annotations

import math
from typing import Any

import pandas as pd

from utils.service_identity import is_infrastructure_service, normalize_service_name
from utils.service_parser import discover_service_metrics, find_metric_column


METRIC_WEIGHTS = {
    "error": 1.4,
    "latency": 1.25,
    "cpu": 1.1,
    "mem": 1.05,
    "load": 1.0,
    "disk": 0.95,
    "socket": 0.95,
    "drop": 0.9,
    "throughput": 0.75,
}


def scan_global_metric_anomalies(
    frame: pd.DataFrame,
    *,
    start: int | None = None,
    end: int | None = None,
    service_metrics: dict[str, list[str]] | None = None,
    top_n: int = 12,
) -> list[dict[str, Any]]:
    if frame.empty or "time" not in frame.columns:
        return []
    service_metrics = service_metrics or discover_service_metrics(frame.columns.tolist())
    rows: list[dict[str, Any]] = []

    for service, metrics in service_metrics.items():
        if is_infrastructure_service(service):
            continue
        metric_rows: list[dict[str, Any]] = []
        total_score = 0.0
        anomalous_metric_count = 0

        for metric in sorted(set(metrics)):
            try:
                column = find_metric_column(frame.columns.tolist(), service, metric)
            except KeyError:
                continue
            metric_score, details = _metric_anomaly_score(frame, column, start=start, end=end)
            if metric_score <= 0:
                continue
            weighted_score = metric_score * METRIC_WEIGHTS.get(metric, 0.85)
            total_score += weighted_score
            anomalous_metric_count += 1
            metric_rows.append(
                {
                    "metric": metric,
                    "column": column,
                    "score": round(weighted_score, 4),
                    **details,
                }
            )

        if not metric_rows:
            continue
        metric_rows.sort(key=lambda item: item["score"], reverse=True)
        rows.append(
            {
                "service": service,
                "normalized_service": normalize_service_name(service),
                "score": round(total_score, 4),
                "anomalous_metric_count": anomalous_metric_count,
                "top_metrics": metric_rows[:5],
            }
        )

    rows.sort(key=lambda item: (item["score"], item["anomalous_metric_count"]), reverse=True)
    return rows[:top_n]


def _metric_anomaly_score(
    frame: pd.DataFrame,
    column: str,
    *,
    start: int | None,
    end: int | None,
) -> tuple[float, dict[str, Any]]:
    values = pd.to_numeric(frame[column], errors="coerce")
    valid = frame[["time"]].copy()
    valid["value"] = values
    valid = valid.dropna(subset=["time", "value"])
    if len(valid) < 4:
        return 0.0, {}

    if start is None:
        return _whole_window_score(valid)

    before = valid[valid["time"] < start]["value"]
    after = valid[valid["time"] >= start]
    if end is not None:
        after = after[after["time"] <= end]
    after_values = after["value"]
    if len(after_values) < 2:
        return _whole_window_score(valid)
    if len(before) < 3:
        before = valid["value"]

    baseline_median = float(before.median())
    baseline_std = float(before.std(ddof=0))
    baseline_mad = float((before - baseline_median).abs().median())
    robust_scale = max(baseline_std, baseline_mad * 1.4826, 1e-9)
    after_max = float(after_values.max())
    after_min = float(after_values.min())
    after_mean = float(after_values.mean())
    baseline_mean = float(before.mean())
    max_deviation = max(abs(after_max - baseline_median), abs(after_min - baseline_median))
    shift = abs(after_mean - baseline_mean)
    z_peak = max_deviation / robust_scale
    z_shift = shift / robust_scale
    spike_count = int(((after_values - baseline_median).abs() / robust_scale >= 2.5).sum())
    if z_peak < 2.0 and z_shift < 1.5 and spike_count == 0:
        return 0.0, {}
    score = min(z_peak, 10.0) + min(z_shift, 6.0) * 0.7 + math.log1p(spike_count)
    return score, {
        "z_peak": round(z_peak, 4),
        "z_shift": round(z_shift, 4),
        "spike_count": spike_count,
        "baseline_mean": round(baseline_mean, 4),
        "after_mean": round(after_mean, 4),
        "after_peak": round(after_max, 4),
    }


def _whole_window_score(valid: pd.DataFrame) -> tuple[float, dict[str, Any]]:
    values = valid["value"]
    std = float(values.std(ddof=0))
    if std <= 1e-12:
        return 0.0, {}
    mean = float(values.mean())
    z_values = ((values - mean) / std).abs()
    z_peak = float(z_values.max())
    spike_count = int((z_values >= 2.5).sum())
    if z_peak < 2.5:
        return 0.0, {}
    score = min(z_peak, 10.0) + math.log1p(spike_count)
    return score, {
        "z_peak": round(z_peak, 4),
        "z_shift": 0.0,
        "spike_count": spike_count,
        "baseline_mean": round(mean, 4),
        "after_mean": round(mean, 4),
        "after_peak": round(float(values.max()), 4),
    }
