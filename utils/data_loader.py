from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from utils.service_parser import discover_service_metrics


class RCAEvalDataLoader:
    def __init__(self, data_path: str | Path):
        self.data_path = Path(data_path)
        if not self.data_path.exists():
            raise FileNotFoundError(f"Data path does not exist: {self.data_path}")
        self.csv_path = self.data_path
        self._metrics_frame: pd.DataFrame | None = None
        self._logs_frame: pd.DataFrame | None = None
        self._traces_frame: pd.DataFrame | None = None
        self._metadata: dict[str, Any] | None = None

    def load_metrics(self) -> pd.DataFrame:
        if self._metrics_frame is None:
            self._metrics_frame = self._read_metrics_frame()
        return self._metrics_frame.copy()

    def load_logs(self) -> pd.DataFrame:
        if self._logs_frame is None:
            self._logs_frame = self._read_optional_frame("logs.csv")
        return self._logs_frame.copy()

    def load_traces(self) -> pd.DataFrame:
        if self._traces_frame is None:
            self._traces_frame = self._read_optional_frame("traces.csv")
        return self._traces_frame.copy()

    def load(self) -> pd.DataFrame:
        return self.load_metrics()

    @property
    def timestamp_column(self) -> str:
        return "time"

    def filter_by_time(self, start: int | None = None, end: int | None = None) -> pd.DataFrame:
        frame = self.load_metrics()
        timestamp_column = self.timestamp_column
        if start is not None:
            frame = frame[frame[timestamp_column] >= start]
        if end is not None:
            frame = frame[frame[timestamp_column] <= end]
        return frame.reset_index(drop=True)

    def get_case_context(self) -> dict[str, Any]:
        metadata = self.get_metadata()
        inject_time = metadata.get("inject_time")
        return {
            **metadata,
            "fault_injection_time": inject_time,
            "metric_services": metadata.get("metric_services", []),
            "metric_service_metrics": metadata.get("service_metrics", {}),
        }

    def get_metadata(self) -> dict[str, Any]:
        if self._metadata is not None:
            return dict(self._metadata)

        metrics_frame = self.load_metrics()
        logs_frame = self.load_logs()
        traces_frame = self.load_traces()
        metadata = self._build_metadata(metrics_frame, logs_frame, traces_frame)
        self._metadata = metadata
        return dict(metadata)

    def _read_metrics_frame(self) -> pd.DataFrame:
        if self.data_path.is_file():
            frame = self._read_tabular_file(self.data_path)
            frame = self._normalize_metrics_frame(frame)
            return self._ensure_sorted(frame)

        metrics_json_path = self.data_path / "metrics.json"
        metrics_csv_path = self.data_path / "metrics.csv"
        simple_metrics_csv_path = self.data_path / "simple_metrics.csv"
        if metrics_json_path.exists():
            frame = self._read_metrics_json(metrics_json_path)
        elif metrics_csv_path.exists():
            frame = self._read_tabular_file(metrics_csv_path)
        elif simple_metrics_csv_path.exists():
            frame = self._read_tabular_file(simple_metrics_csv_path)
        else:
            csv_candidates = [
                path
                for path in sorted(self.data_path.glob("*.csv"))
                if path.name.lower() not in {"logs.csv", "traces.csv"}
            ]
            if not csv_candidates:
                raise FileNotFoundError(f"No metrics file found under: {self.data_path}")
            frame = self._read_tabular_file(csv_candidates[0])
        frame = self._normalize_metrics_frame(frame)
        return self._ensure_sorted(frame)

    def _read_optional_frame(self, filename: str) -> pd.DataFrame:
        if self.data_path.is_file():
            return pd.DataFrame()
        file_path = self.data_path / filename
        if not file_path.exists():
            return pd.DataFrame()
        frame = self._read_tabular_file(file_path)
        return self._ensure_sorted(frame)

    def _read_tabular_file(self, file_path: Path) -> pd.DataFrame:
        if file_path.suffix.lower() == ".json":
            return self._read_metrics_json(file_path)
        return pd.read_csv(file_path)

    def _read_metrics_json(self, file_path: Path) -> pd.DataFrame:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            if "data" in raw and isinstance(raw["data"], list):
                raw = raw["data"]
            else:
                raw = [raw]
        frame = pd.json_normalize(raw)
        if "time" not in frame.columns:
            raise ValueError(f"metrics.json must contain a time field: {file_path}")
        return frame

    def _normalize_metrics_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        frame = frame.copy()
        if "time" not in frame.columns:
            timestamp_candidates = [column for column in frame.columns if column.lower() in {"time", "timestamp"}]
            if not timestamp_candidates:
                raise ValueError("No timestamp column found in metrics data.")
            frame = frame.rename(columns={timestamp_candidates[0]: "time"})
        frame["time"] = pd.to_numeric(frame["time"], errors="coerce")
        frame = frame.dropna(subset=["time"]).copy()
        frame["time"] = frame["time"].astype("int64")
        return frame

    @staticmethod
    def _ensure_sorted(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return frame.reset_index(drop=True)
        return frame.sort_values(by="time").reset_index(drop=True)

    def _build_metadata(
        self,
        metrics_frame: pd.DataFrame,
        logs_frame: pd.DataFrame,
        traces_frame: pd.DataFrame,
    ) -> dict[str, Any]:
        service_metrics = self._discover_service_metrics(metrics_frame.columns.tolist())
        services = sorted(service_metrics.keys())
        metadata: dict[str, Any] = {
            "data_path": str(self.data_path),
            "dataset_kind": "case" if self.data_path.is_dir() else "file",
            "rows": int(len(metrics_frame)),
            "columns": metrics_frame.columns.tolist(),
            "metric_columns": [column for column in metrics_frame.columns.tolist() if column != "time"],
            "timestamp_column": "time",
            "start_time": int(metrics_frame["time"].min()) if not metrics_frame.empty else None,
            "end_time": int(metrics_frame["time"].max()) if not metrics_frame.empty else None,
            "services": services,
            "service_metrics": service_metrics,
            "metric_services": services,
            "service_count": len(services),
            "metric_count": sum(len(metrics) for metrics in service_metrics.values()),
            "metric_column_count": len(metrics_frame.columns) - (1 if "time" in metrics_frame.columns else 0),
            "log_rows": int(len(logs_frame)),
            "trace_rows": int(len(traces_frame)),
            "has_effective_logs": not logs_frame.empty,
            "has_effective_traces": not traces_frame.empty,
        }
        inject_time = self._read_inject_time()
        if inject_time is not None:
            metadata["inject_time"] = inject_time
        if self.data_path.is_file():
            metadata["csv_path"] = str(self.data_path)
        return metadata

    def _read_inject_time(self) -> int | None:
        if self.data_path.is_file():
            return None
        inject_path = self.data_path / "inject_time.txt"
        if not inject_path.exists():
            return None
        try:
            return int(inject_path.read_text(encoding="utf-8").strip())
        except ValueError:
            return None

    @staticmethod
    def _discover_service_metrics(columns: list[str]) -> dict[str, list[str]]:
        return discover_service_metrics(columns)



CSVDataLoader = RCAEvalDataLoader
