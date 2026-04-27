from __future__ import annotations

from typing import Any

import pandas as pd

from utils.data_loader import CSVDataLoader


def build_dataset_summary(loader: CSVDataLoader, start: int | None = None, end: int | None = None) -> dict[str, Any]:
    metadata = loader.get_metadata()
    window = loader.filter_by_time(start=start, end=end)
    timestamp_column = loader.timestamp_column
    return {
        **metadata,
        "window_rows": int(len(window)),
        "window_start": int(window[timestamp_column].min()) if not window.empty else None,
        "window_end": int(window[timestamp_column].max()) if not window.empty else None,
    }


def frame_to_records(frame: pd.DataFrame, limit: int = 20) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    return frame.head(limit).to_dict(orient="records")
