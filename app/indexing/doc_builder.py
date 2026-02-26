"""app.indexing.doc_builder

Builds Azure AI Search documents from Excel rows.
"""

from __future__ import annotations
from typing import Any
import pandas as pd


class DocBuilder:
    """Transforms loaded DataFrames into doc lists for AI Search."""

    @staticmethod
    def _yn(val: Any) -> str:
        s = str(val).strip().lower()
        return "yes" if s in ("1", "true", "yes", "y") else "no"

    def build(self, excel_data: dict[str, pd.DataFrame]) -> dict[str, list[dict[str, Any]]]:
        field_df = excel_data["field"]
        table_df = excel_data["table"]
        rel_df = excel_data["relationship"]

        field_docs: list[dict[str, Any]] = []
        for _, r in field_df.iterrows():
            schema = str(r.get("SCHEMA_NAME", "")).strip()
            table = str(r.get("TABLE_NAME", "")).strip()
            col = str(r.get("COLUMN_NAME", "")).strip()
            doc_id = f"{schema}.{table}.{col}".lower()
            content = (
                f"schema {schema} table {table} column {col}. "
                f"business_name: {r.get('BUSINESS_NAME','')}. "
                f"business_description: {r.get('BUSINESS_DESCRIPTION','')}. "
                f"data_type: {r.get('DATA_TYPE','')}. "
                f"pii: {self._yn(r.get('PII','no'))}. pci: {self._yn(r.get('PCI','no'))}."
            )
            field_docs.append({
                "id": doc_id,
                "schema_name": schema,
                "table_name": table,
                "column_name": col,
                "business_name": str(r.get("BUSINESS_NAME", "")),
                "business_description": str(r.get("BUSINESS_DESCRIPTION", "")),
                "data_type": str(r.get("DATA_TYPE", "")),
                "pii": self._yn(r.get("PII", "no")),
                "pci": self._yn(r.get("PCI", "no")),
                "content": content,
            })

        table_docs: list[dict[str, Any]] = []
        for _, r in table_df.iterrows():
            schema = str(r.get("SCHEMA_NAME", "")).strip()
            table = str(r.get("TABLE_NAME", "")).strip()
            doc_id = f"{schema}.{table}".lower()
            content = (
                f"schema {schema} table {table}. "
                f"table_business_name: {r.get('TABLE_BUSINESS_NAME','')}. "
                f"table_business_description: {r.get('TABLE_BUSINESS_DESCRIPTION','')}. "
            )
            table_docs.append({
                "id": doc_id,
                "schema_name": schema,
                "table_name": table,
                "table_business_name": str(r.get("TABLE_BUSINESS_NAME", "")),
                "table_business_description": str(r.get("TABLE_BUSINESS_DESCRIPTION", "")),
                "content": content,
            })

        rel_docs: list[dict[str, Any]] = []
        for _, r in rel_df.iterrows():
            fs = str(r.get("FROM_SCHEMA", "")).strip()
            ft = str(r.get("FROM_TABLE", "")).strip()
            ts = str(r.get("TO_SCHEMA", "")).strip()
            tt = str(r.get("TO_TABLE", "")).strip()
            doc_id = f"{fs}.{ft}->{ts}.{tt}".lower()
            content = (
                f"from {fs}.{ft} to {ts}.{tt}. "
                f"join_type: {r.get('JOIN_TYPE','')}. "
                f"join_keys: {r.get('JOIN_KEYS','')}. "
            )
            rel_docs.append({
                "id": doc_id,
                "from_schema": fs,
                "from_table": ft,
                "to_schema": ts,
                "to_table": tt,
                "join_type": str(r.get("JOIN_TYPE", "")),
                "join_keys": str(r.get("JOIN_KEYS", "")),
                "content": content,
            })

        return {"field": field_docs, "table": table_docs, "relationship": rel_docs}
