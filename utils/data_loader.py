from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from utils.service_parser import discover_service_metrics, discover_services, normalize_timestamp_column


class CSVDataLoader:
    def __init__(self, csv_path: str | Path):
        self.csv_path = Path(csv_path)
        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV file does not exist: {self.csv_path}")
        self._frame: pd.DataFrame | None = None
        self._timestamp_column: str | None = None

    def load(self) -> pd.DataFrame:
        if self._frame is None:
            frame = pd.read_csv(self.csv_path)
            if frame.empty:
                raise ValueError(f"CSV file is empty: {self.csv_path}")
            self._timestamp_column = normalize_timestamp_column(frame.columns.tolist())
            frame[self._timestamp_column] = pd.to_numeric(frame[self._timestamp_column], errors="coerce")
            frame = frame.dropna(subset=[self._timestamp_column]).copy()
            frame[self._timestamp_column] = frame[self._timestamp_column].astype("int64")
            frame = frame.sort_values(by=self._timestamp_column).reset_index(drop=True)
            self._frame = frame
        return self._frame.copy()

    @property
    def timestamp_column(self) -> str:
        self.load()
        if not self._timestamp_column:
            raise ValueError("Timestamp column has not been initialized.")
        return self._timestamp_column

    def filter_by_time(self, start: int | None = None, end: int | None = None) -> pd.DataFrame:
        frame = self.load()
        timestamp_column = self.timestamp_column
        if start is not None:
            frame = frame[frame[timestamp_column] >= start]
        if end is not None:
            frame = frame[frame[timestamp_column] <= end]
        return frame.reset_index(drop=True)

    def get_metadata(self) -> dict[str, Any]:
        frame = self.load()
        services = discover_services(frame.columns.tolist())
        service_metrics = discover_service_metrics(frame.columns.tolist())
        timestamp_column = self.timestamp_column
        return {
            "csv_path": str(self.csv_path),
            "rows": int(len(frame)),
            "columns": frame.columns.tolist(),
            "timestamp_column": timestamp_column,
            "start_time": int(frame[timestamp_column].min()),
            "end_time": int(frame[timestamp_column].max()),
            "services": services,
            "service_metrics": service_metrics,
        }
