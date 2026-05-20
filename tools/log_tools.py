from __future__ import annotations

from typing import Any

import pandas as pd

from utils.data_loader import CSVDataLoader


class LogToolbox:
    def __init__(self, loader: CSVDataLoader):
        self.loader = loader

    def query_service_logs(
        self,
        service: str,
        start: int | None = None,
        end: int | None = None,
    ) -> list[dict[str, Any]]:
        frame = self.loader.load_logs()
        if frame.empty:
            return []
        normalized = self._normalize_log_frame(frame)
        if normalized.empty:
            return []
        if "service" in normalized.columns:
            normalized = normalized[normalized["service"].astype(str).str.lower() == service.lower()]
        if normalized.empty:
            return []
        if start is not None:
            normalized = normalized[normalized["timestamp"] >= start]
        if end is not None:
            normalized = normalized[normalized["timestamp"] <= end]
        return normalized.sort_values(by="timestamp").to_dict(orient="records")

    def summarize_logs(
        self,
        service: str,
        start: int | None = None,
        end: int | None = None,
    ) -> dict[str, Any]:
        logs = self.query_service_logs(service=service, start=start, end=end)
        patterns: dict[str, int] = {}
        for log in logs:
            key = str(log.get("level") or log.get("severity") or log.get("pattern") or "log")
            patterns[key] = patterns.get(key, 0) + 1
        top_patterns = sorted(patterns.items(), key=lambda item: item[1], reverse=True)
        return {
            "service": service,
            "pillar": "log",
            "source_type": "real" if logs else "missing",
            "time_aligned": bool(logs),
            "strength": "strong" if len(logs) >= 10 else "medium" if logs else "weak",
            "log_count": len(logs),
            "top_patterns": [{"pattern": key, "count": count} for key, count in top_patterns[:5]],
            "sample_logs": logs[:10],
        }

    @staticmethod
    def _normalize_log_frame(frame):
        normalized = frame.copy()
        rename_map = {}
        canonical_seen: set[str] = set()
        for column in normalized.columns:
            lowered = column.lower()
            if lowered in {"time", "timestamp"}:
                canonical = "timestamp"
            elif lowered in {"level", "severity"}:
                canonical = "level"
            elif lowered in {"service", "container_name", "pod_name"}:
                canonical = "service"
            elif lowered in {"msg", "content", "event", "message"}:
                canonical = "message"
            else:
                canonical = ""
            if canonical and canonical not in canonical_seen:
                rename_map[column] = canonical
                canonical_seen.add(canonical)
        normalized = normalized.rename(columns=rename_map)
        normalized = normalized.loc[:, ~normalized.columns.duplicated()]
        if "timestamp" not in normalized.columns:
            return normalized.iloc[0:0]
        normalized["timestamp"] = pd.to_numeric(normalized["timestamp"], errors="coerce")
        normalized = normalized.dropna(subset=["timestamp"]).copy()
        normalized["timestamp"] = normalized["timestamp"].astype("int64")
        if "message" not in normalized.columns:
            normalized["message"] = normalized.apply(lambda row: " | ".join(str(value) for value in row.values[:3]), axis=1)
        if "level" not in normalized.columns:
            normalized["level"] = "INFO"
        return normalized
