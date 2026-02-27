"""app.available_data.engine

Answers questions from "currently available" datasets (in-memory).

Guardrails:
- Never return raw full datasets to UI; always cap rows/cols.
- Prefer showing trend slices (e.g., last 12 months) and key KPIs.

Important:
- Datasets are summarized already; we avoid aggregation (no group-by).
- We do allow *filtering* and *windowing* (latest date, last N months/weeks).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd

from app.available_data.store import AvailableDataStore
from app.available_data.registry import IntentRegistry
from app.available_data.finder import DatasetMetricMatch, find_dataset_and_metrics


@dataclass
class AvailableAnswer:
    ok: bool
    reason: str
    dataset: Optional[str]
    df: Optional[pd.DataFrame]
    time_col: Optional[str]
    metric_cols: list[str]


def _latest_window(df: pd.DataFrame, time_col: str, window_size: int) -> pd.DataFrame:
    try:
        dd = df.copy()
        dd[time_col] = pd.to_datetime(dd[time_col], errors="coerce")
        dd = dd.dropna(subset=[time_col]).sort_values(time_col)
        unique_times = dd[time_col].drop_duplicates().tail(window_size)
        return dd[dd[time_col].isin(unique_times)].copy()
    except Exception:
        return df.tail(window_size)


class AvailableDataEngine:
    def __init__(self, store: AvailableDataStore, registry: IntentRegistry):
        self.store = store
        self.registry = registry

    def answer_from_intent(self, intent_key: str, question: str) -> AvailableAnswer:
        spec = self.registry.get(intent_key)
        if not spec:
            return AvailableAnswer(False, "Intent not found in registry", None, None, None, [])

        ds = str(spec.get("dataset", "")).strip()
        if not ds:
            return AvailableAnswer(False, "Intent has no dataset mapping", None, None, None, [])

        if not self.store.has_dataset(ds):
            return AvailableAnswer(False, f"Dataset not available: {ds}", ds, None, None, [])

        df = self.store.get_df(ds)
        required = [str(c) for c in spec.get("required_columns", [])]
        missing = [c for c in required if c not in df.columns]
        if missing:
            return AvailableAnswer(False, f"Missing required columns: {missing}", ds, None, None, [])

        # Determine time column
        time_col = None
        for tc in ["as_of_date", "as_of_week", "as_of_month"]:
            if tc in df.columns:
                time_col = tc
                break

        # Windowing
        filters = spec.get("default_filters", {}) or {}
        if time_col and "window_months" in filters:
            df2 = _latest_window(df, time_col, int(filters["window_months"]))
        elif time_col and "window_weeks" in filters:
            df2 = _latest_window(df, time_col, int(filters["window_weeks"]))
        elif time_col and "window_days" in filters:
            df2 = _latest_window(df, time_col, int(filters["window_days"]))
        elif time_col and filters.get(time_col) == "LATEST":
            df2 = _latest_window(df, time_col, 1)
        else:
            df2 = df

        # Metric columns (simple: all numeric except coordinates/ids)
        metric_cols = []
        for c in df2.columns:
            if c in ("lat", "lon"):
                continue
            if pd.api.types.is_numeric_dtype(df2[c]):
                metric_cols.append(c)

        return AvailableAnswer(True, "ok", ds, df2, time_col, metric_cols)

    def answer_from_free_question(self, question: str) -> AvailableAnswer:
        match: Optional[DatasetMetricMatch] = find_dataset_and_metrics(self.store, question)
        if not match:
            return AvailableAnswer(False, "No suitable dataset/metric found", None, None, None, [])

        df = self.store.get_df(match.dataset)
        df2 = df

        # Window default: last 12 points
        df2 = _latest_window(df2, match.time_col, 12)

        # Keep only needed cols (+ lat/lon if present)
        keep = [match.time_col] + match.metric_cols
        for c in ["lat", "lon", "branch_name", "region", "product", "service"]:
            if c in df2.columns and c not in keep:
                keep.append(c)
        df2 = df2[keep].copy()

        return AvailableAnswer(True, match.reason, match.dataset, df2, match.time_col, match.metric_cols)
