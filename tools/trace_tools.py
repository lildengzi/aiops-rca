from __future__ import annotations

from typing import Any

import pandas as pd

from tools.log_tools import LogToolbox
from tools.topology_tools import TopologyToolbox
from utils.data_loader import CSVDataLoader


class TraceToolbox:
    def __init__(self, loader: CSVDataLoader):
        self.loader = loader
        self.log_toolbox = LogToolbox(loader)
        self.topology_toolbox = TopologyToolbox(loader)

    def query_service_traces(
        self,
        service: str,
        start: int | None = None,
        end: int | None = None,
    ) -> list[dict[str, Any]]:
        frame = self.loader.load_traces()
        if not frame.empty:
            normalized = self._normalize_trace_frame(frame)
            if "service" in normalized.columns:
                normalized = normalized[normalized["service"].astype(str).str.lower() == service.lower()]
            start, end = self._normalize_time_window(normalized, start, end)
            if start is not None:
                normalized = normalized[normalized["timestamp"] >= start]
            if end is not None:
                normalized = normalized[normalized["timestamp"] <= end]
            if not normalized.empty:
                records = normalized.sort_values(by="timestamp").to_dict(orient="records")
                for record in records:
                    record.setdefault("service", service)
                    record["trace_source"] = "real"
                    record["pillar"] = "trace"
                    record["source_type"] = "real"
                    record["time_aligned"] = True
                    record["strength"] = "strong"
                return records

        topology = self.topology_toolbox.get_full_topology()
        topology_details = self.topology_toolbox.get_topology_details()
        reverse_topology = self.topology_toolbox.reverse_topology()
        log_summary = self.log_toolbox.summarize_logs(service, start=start, end=end)
        upstream = reverse_topology.get(service, [])
        downstream = topology.get(service, [])
        service_type = topology_details.get(service, {}).get("type", "application")

        traces: list[dict[str, Any]] = []
        root_candidates = upstream or [service]

        for source in root_candidates:
            path = [source] if source == service else [source, service]
            for dependency in downstream[:2]:
                if dependency not in path:
                    path.append(dependency)
            traces.append(
                {
                    "entry_service": path[0],
                    "suspect_service": service,
                    "path": path,
                    "log_count": log_summary.get("log_count"),
                    "service_type": service_type,
                    "upstream_services": upstream,
                    "downstream_services": downstream,
                    "trace_source": "topology_inferred",
                    "pillar": "topology",
                    "source_type": "inferred",
                    "time_aligned": "unknown",
                    "strength": "weak",
                }
            )

        return traces[:5]

    def summarize_traces(
        self,
        service: str,
        start: int | None = None,
        end: int | None = None,
    ) -> dict[str, Any]:
        traces = self.query_service_traces(service=service, start=start, end=end)
        real_traces = [item for item in traces if item.get("source_type") == "real"]
        inferred_traces = [item for item in traces if item.get("source_type") == "inferred"]
        propagation_paths = []
        for item in traces:
            path = item.get("path")
            if isinstance(path, list) and path:
                propagation_paths.append(" -> ".join(str(part) for part in path))
            elif item.get("service"):
                propagation_paths.append(str(item["service"]))
        if real_traces:
            pillar = "trace"
            source_type = "real"
            trace_count = len(real_traces)
            topology_count = 0
            strength = "strong"
            time_aligned: bool | str = True
        elif inferred_traces:
            pillar = "topology"
            source_type = "inferred"
            trace_count = 0
            topology_count = len(inferred_traces)
            strength = "weak"
            time_aligned = "unknown"
        else:
            pillar = "trace"
            source_type = "missing"
            trace_count = 0
            topology_count = 0
            strength = "weak"
            time_aligned = "unknown"
        return {
            "service": service,
            "pillar": pillar,
            "source_type": source_type,
            "time_aligned": time_aligned,
            "strength": strength,
            "trace_count": trace_count,
            "topology_count": topology_count,
            "propagation_paths": propagation_paths,
            "sample_traces": traces,
        }

    @staticmethod
    def _normalize_trace_frame(frame):
        normalized = frame.copy()
        rename_map: dict[str, str] = {}
        canonical_seen: set[str] = set()
        timestamp_column = TraceToolbox._select_timestamp_column(normalized)
        if not timestamp_column:
            return normalized.iloc[0:0]
        rename_map[timestamp_column] = "timestamp"
        canonical_seen.add("timestamp")
        for column in normalized.columns:
            if column == timestamp_column:
                continue
            lowered = column.lower()
            if lowered in {"service", "span_service", "span", "operation", "servicename", "container_name"}:
                canonical = "service"
            elif lowered in {"trace_id", "span_id", "parent_span_id", "duration", "latency"}:
                canonical = lowered
            elif lowered in {"traceid", "spanid", "parentspanid"}:
                canonical = {
                    "traceid": "trace_id",
                    "spanid": "span_id",
                    "parentspanid": "parent_span_id",
                }[lowered]
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
        return normalized

    @staticmethod
    def _select_timestamp_column(frame: pd.DataFrame) -> str | None:
        columns_by_lower = {column.lower(): column for column in frame.columns}
        for candidate in ("starttimemillis", "starttime", "timestamp", "time"):
            column = columns_by_lower.get(candidate)
            if not column:
                continue
            numeric = pd.to_numeric(frame[column], errors="coerce")
            if numeric.notna().any():
                return column
        return None

    @staticmethod
    def _normalize_time_window(
        frame: pd.DataFrame,
        start: int | None,
        end: int | None,
    ) -> tuple[int | None, int | None]:
        if frame.empty or "timestamp" not in frame.columns:
            return start, end
        timestamp_max = pd.to_numeric(frame["timestamp"], errors="coerce").max()
        if pd.isna(timestamp_max):
            return start, end
        # RCAEval inject_time.txt is second-level in several datasets while
        # trace timestamps are millisecond-level. Align before filtering.
        if int(timestamp_max) >= 10_000_000_000:
            if start is not None and start < 10_000_000_000:
                start = start * 1000
            if end is not None and end < 10_000_000_000:
                end = end * 1000
        return start, end
