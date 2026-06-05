from __future__ import annotations

from typing import Any

import pandas as pd

from utils.data_loader import CSVDataLoader
from utils.log_template_anomaly import scan_log_template_anomalies
from utils.service_identity import services_equivalent


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
        template_summary = self.summarize_log_templates(service=service, start=start, end=end)
        patterns: dict[str, int] = {}
        for log in logs:
            key = str(log.get("level") or log.get("severity") or log.get("pattern") or "log")
            patterns[key] = patterns.get(key, 0) + 1
        top_patterns = sorted(patterns.items(), key=lambda item: item[1], reverse=True)
        log_count = len(logs)
        template_score = float(template_summary.get("template_anomaly_score", 0.0) or 0.0)
        source_type = "real" if logs or template_score > 0 else "missing"
        strength = "strong" if log_count >= 10 or template_score >= 10 else "medium" if logs or template_score > 0 else "weak"
        return {
            "service": service,
            "pillar": "log",
            "source_type": source_type,
            "time_aligned": bool(logs) or template_score > 0,
            "strength": strength,
            "log_count": log_count,
            "top_patterns": [{"pattern": key, "count": count} for key, count in top_patterns[:5]],
            **template_summary,
            "sample_logs": logs[:10],
        }

    def summarize_log_templates(
        self,
        service: str,
        start: int | None = None,
        end: int | None = None,
    ) -> dict[str, Any]:
        frame = self.loader.load_log_templates()
        if frame.empty:
            return {
                "template_anomaly_score": 0.0,
                "anomalous_template_count": 0,
                "new_template_count": 0,
                "top_templates": [],
            }
        matches = [
            item
            for item in scan_log_template_anomalies(frame, start=start, end=end, top_n=100)
            if services_equivalent(str(item.get("service") or ""), service)
        ]
        if not matches:
            return {
                "template_anomaly_score": 0.0,
                "anomalous_template_count": 0,
                "new_template_count": 0,
                "top_templates": [],
            }
        merged_score = sum(float(item.get("score", 0.0) or 0.0) for item in matches)
        templates = [
            template
            for item in matches
            for template in item.get("top_templates", [])
            if isinstance(template, dict)
        ]
        templates.sort(key=lambda item: float(item.get("score", 0.0) or 0.0), reverse=True)
        return {
            "template_anomaly_score": round(merged_score, 4),
            "anomalous_template_count": sum(int(item.get("anomalous_template_count", 0) or 0) for item in matches),
            "new_template_count": sum(int(item.get("new_template_count", 0) or 0) for item in matches),
            "top_templates": templates[:5],
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
