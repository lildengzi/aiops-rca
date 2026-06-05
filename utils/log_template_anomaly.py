from __future__ import annotations

import math
from typing import Any

import pandas as pd

from utils.global_anomaly import _metric_anomaly_score
from utils.service_identity import is_infrastructure_service, normalize_service_name


def scan_log_template_anomalies(
    frame: pd.DataFrame,
    *,
    start: int | None = None,
    end: int | None = None,
    top_n: int = 12,
) -> list[dict[str, Any]]:
    if frame.empty or "time" not in frame.columns:
        return []

    grouped: dict[str, list[tuple[str, str]]] = {}
    for column in frame.columns:
        parsed = split_log_template_column(column)
        if not parsed:
            continue
        service, template_id = parsed
        if is_infrastructure_service(service):
            continue
        grouped.setdefault(service, []).append((column, template_id))

    rows: list[dict[str, Any]] = []
    for service, columns in grouped.items():
        template_rows: list[dict[str, Any]] = []
        total_score = 0.0
        new_template_count = 0

        for column, template_id in columns:
            score, details = _template_score(frame, column, start=start, end=end)
            if score <= 0:
                continue
            if details.get("new_template"):
                new_template_count += 1
            total_score += score
            template_rows.append(
                {
                    "template": f"{service}_{template_id}",
                    "column": column,
                    "score": round(score, 4),
                    **details,
                }
            )

        if not template_rows:
            continue
        template_rows.sort(key=lambda item: item["score"], reverse=True)
        rows.append(
            {
                "service": service,
                "normalized_service": normalize_service_name(service),
                "score": round(total_score, 4),
                "anomalous_template_count": len(template_rows),
                "new_template_count": new_template_count,
                "top_templates": template_rows[:5],
            }
        )

    rows.sort(key=lambda item: (item["score"], item["anomalous_template_count"]), reverse=True)
    return rows[:top_n]


def split_log_template_column(column: str) -> tuple[str, str] | None:
    text = str(column)
    if text.lower() == "time" or "_" not in text:
        return None
    service, template_id = text.rsplit("_", 1)
    if not service or not template_id.isdigit():
        return None
    return service, template_id


def _template_score(
    frame: pd.DataFrame,
    column: str,
    *,
    start: int | None,
    end: int | None,
) -> tuple[float, dict[str, Any]]:
    score, details = _metric_anomaly_score(frame[["time", column]], column, start=start, end=end)
    values = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    if start is None:
        return score * 0.75, {**details, "new_template": False}

    before = values[frame["time"] < start]
    after_frame = frame[frame["time"] >= start]
    if end is not None:
        after_frame = after_frame[after_frame["time"] <= end]
    after = pd.to_numeric(after_frame[column], errors="coerce").fillna(0.0)
    if after.empty:
        return score, {**details, "new_template": False}

    before_max = float(before.max()) if not before.empty else 0.0
    after_max = float(after.max())
    after_sum = float(after.sum())
    new_template = before_max <= 0 and after_max > 0
    burst_score = math.log1p(after_sum) if new_template else 0.0
    final_score = score + min(burst_score, 6.0)
    return final_score, {
        **details,
        "new_template": new_template,
        "before_max": round(before_max, 4),
        "after_max": round(after_max, 4),
        "after_sum": round(after_sum, 4),
    }
