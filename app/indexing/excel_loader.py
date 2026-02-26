"""app.indexing.excel_loader

Loads and validates metadata Excel.
"""

from __future__ import annotations
import pandas as pd
from app.indexing.excel_schema import REQUIRED_SHEETS, FIELD_REQUIRED_COLUMNS, TABLE_REQUIRED_COLUMNS, REL_REQUIRED_COLUMNS


class ExcelLoader:
    """Loads metadata Excel into DataFrames and validates required columns."""

    def load(self, path: str) -> dict[str, pd.DataFrame]:
        xl = pd.ExcelFile(path)
        sheets = xl.sheet_names
        missing_sheets = [s for s in REQUIRED_SHEETS if s not in sheets]
        if missing_sheets:
            raise ValueError(f"Missing required sheet(s): {missing_sheets}")

        field_df = xl.parse("field").fillna("")
        table_df = xl.parse("table").fillna("")
        rel_df = xl.parse("relationship").fillna("")

        self._validate_cols(field_df, FIELD_REQUIRED_COLUMNS, "field")
        self._validate_cols(table_df, TABLE_REQUIRED_COLUMNS, "table")
        self._validate_cols(rel_df, REL_REQUIRED_COLUMNS, "relationship")

        return {"field": field_df, "table": table_df, "relationship": rel_df}

    @staticmethod
    def _validate_cols(df: pd.DataFrame, required: list[str], sheet: str) -> None:
        cols = {str(c).strip().upper() for c in df.columns}
        missing = [c for c in required if c.upper() not in cols]
        if missing:
            raise ValueError(f"Sheet '{sheet}' missing required columns: {missing}")
