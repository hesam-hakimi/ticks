"""app.policy.limits_policy

Applies row limits (TOP/LIMIT) and truncates results for UI safety.
"""

from __future__ import annotations
import re
from typing import Any, Tuple, List


class LimitsPolicy:
    """Applies row limits and truncation rules."""

    _select_re = re.compile(r"^\s*select\s+", re.IGNORECASE)

    def apply_row_limit(self, sql: str, backend: str, max_rows: int) -> str:
        """Ensure query has TOP/LIMIT for safety."""
        s = (sql or "").strip().rstrip(";")

        if backend == "sqlserver":
            if re.search(r"\btop\s+\(?\s*\d+\s*\)?", s, re.IGNORECASE):
                return s
            return self._select_re.sub(f"SELECT TOP ({max_rows}) ", s, count=1)

        # sqlite
        if re.search(r"\blimit\s+\d+\b", s, re.IGNORECASE):
            return s
        return f"{s} LIMIT {max_rows}"

    def truncate_result(self, columns: List[str], rows: List[List[Any]], max_cols: int, max_rows: int) -> Tuple[List[str], List[List[Any]], bool]:
        """Truncate result in-memory for UI safety."""
        truncated = False

        if len(columns) > max_cols:
            columns = columns[:max_cols]
            rows = [r[:max_cols] for r in rows]
            truncated = True

        if len(rows) > max_rows:
            rows = rows[:max_rows]
            truncated = True

        return columns, rows, truncated
