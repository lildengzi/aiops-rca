from __future__ import annotations

from typing import Iterable

import pandas as pd


def detect_anomaly_zscore(series: pd.Series, threshold: float = 2.5) -> list[int]:
    numeric = pd.to_numeric(series, errors="coerce").fillna(0.0)
    if numeric.empty:
        return []
    std = float(numeric.std(ddof=0))
    if std == 0:
        return []
    mean = float(numeric.mean())
    zscores = ((numeric - mean) / std).abs()
    return [int(idx) for idx, score in enumerate(zscores.tolist()) if score >= threshold]


def summarize_series(series: pd.Series) -> dict[str, float | int | None]:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return {
            "count": 0,
            "mean": None,
            "max": None,
            "min": None,
            "std": None,
        }
    return {
        "count": int(numeric.count()),
        "mean": float(numeric.mean()),
        "max": float(numeric.max()),
        "min": float(numeric.min()),
        "std": float(numeric.std(ddof=0)),
    }


def top_anomaly_ratio(anomaly_indices: Iterable[int], total_count: int) -> float:
    if total_count <= 0:
        return 0.0
    unique_count = len(set(int(index) for index in anomaly_indices))
    return unique_count / total_count
