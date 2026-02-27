"""app.available_data.finder

Finds the best dataset + metric columns when a question doesn't match a known intent.

Requirement:
- The user can ask questions not present in the intent registry.
- If data exists in the "currently available" datasets, still answer and create visuals.

Approach:
- Deterministic synonym mapping for common manager terms (satisfaction->nps, churn->churn_rate, etc.)
- Light fuzzy matching to pick a metric when no synonym matches
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

from app.available_data.store import AvailableDataStore


TIME_COL_CANDIDATES = ["as_of_date", "as_of_week", "as_of_month", "date", "week", "month"]

SYNONYMS = {
    "customer satisfaction": ["nps"],
    "satisfaction": ["nps"],
    "nps": ["nps"],
    "churn": ["churn_rate", "churn_pct"],
    "retention": ["retention_rate"],
    "latency": ["p95_latency_ms"],
    "incidents": ["incident_count"],
    "uptime": ["uptime"],
    "deposits": ["total_deposits", "deposits", "balance"],
    "loans": ["total_loans"],
    "net income": ["net_income"],
    "revenue": ["net_revenue"],
    "efficiency": ["efficiency_ratio"],
    "risk": ["risk_score", "npl_ratio"],
    "credit quality": ["npl_ratio", "stage2_ratio"],
}


@dataclass
class DatasetMetricMatch:
    dataset: str
    time_col: str
    metric_cols: list[str]
    score: float
    reason: str


def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def find_dataset_and_metrics(store: AvailableDataStore, question: str) -> Optional[DatasetMetricMatch]:
    q = question.lower()

    desired: list[str] = []
    for k, cols in SYNONYMS.items():
        if k in q:
            desired.extend(cols)

    best: Optional[DatasetMetricMatch] = None

    for ds in store.list_datasets():
        original_cols = store.schema(ds)
        cols = [c.lower() for c in original_cols]

        # time column
        time_col = None
        for tc in TIME_COL_CANDIDATES:
            if tc in cols:
                time_col = original_cols[cols.index(tc)]
                break
        if not time_col:
            continue

        # metric candidates via synonyms
        metric: list[str] = []
        for want in desired:
            if want.lower() in cols:
                metric.append(original_cols[cols.index(want.lower())])

        # fallback: fuzzy pick top 1-2 columns related to question words
        if not metric:
            words = [w for w in re.split(r"\W+", q) if w]
            scored: list[tuple[float, str]] = []
            for c in original_cols:
                s = max((_sim(w, c) for w in words), default=0.0)
                scored.append((s, c))
            scored.sort(reverse=True)
            metric = [c for s, c in scored[:2] if s >= 0.65]

        if not metric:
            continue

        score = len(metric) * 1.0 + max((_sim(m, question) for m in metric), default=0.0)
        reason = f"time={time_col}; metrics={metric}"
        cand = DatasetMetricMatch(dataset=ds, time_col=time_col, metric_cols=metric, score=score, reason=reason)
        if not best or cand.score > best.score:
            best = cand

    return best
