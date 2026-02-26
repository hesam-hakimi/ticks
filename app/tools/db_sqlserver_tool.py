"""app.tools.db_sqlserver_tool

SQL Server execution tool (read-only) using **MSI**.

Uses pyodbc. Recommended MSI connection string pattern (ODBC Driver 18):
  Driver={ODBC Driver 18 for SQL Server};
  Server=tcp:<server>.database.windows.net,1433;
  Database=<db>;
  Encrypt=yes;
  TrustServerCertificate=no;
  Authentication=ActiveDirectoryMsi;
  UID=<user-assigned-msi-client-id>;   # optional for user-assigned MSI

Safety is enforced by SqlPolicy.
"""

from __future__ import annotations
import time
from typing import Any, Optional
import os
import pyodbc


class SqlServerDatabaseTool:
    """Read-only SQL execution wrapper for Azure SQL."""

    def __init__(self, server: Optional[str], database: Optional[str], conn_str: Optional[str], logger):
        self.server = server
        self.database = database
        self.conn_str = conn_str
        self.logger = logger

    def _build_conn_str(self) -> str:
        if self.conn_str:
            return self.conn_str

        if not self.server or not self.database:
            raise ValueError("AZURE_SQL_SERVER/AZURE_SQL_DATABASE or AZURE_SQL_CONN_STR must be set")

        client_id = (os.getenv("AZURE_MSI_CLIENT_ID") or "").strip()
        uid_part = f"UID={client_id};" if client_id else ""

        return (
            "Driver={ODBC Driver 18 for SQL Server};"
            f"Server=tcp:{self.server},1433;"
            f"Database={self.database};"
            "Encrypt=yes;"
            "TrustServerCertificate=no;"
            "Authentication=ActiveDirectoryMsi;"
            f"{uid_part}"
        )

    def execute(self, sql: str, timeout_seconds: int) -> dict[str, Any]:
        start = time.time()
        conn = None
        try:
            conn = pyodbc.connect(self._build_conn_str(), timeout=timeout_seconds)
            cur = conn.cursor()
            cur.timeout = timeout_seconds
            cur.execute(sql)
            columns = [c[0] for c in cur.description] if cur.description else []
            rows = cur.fetchall() if cur.description else []
            elapsed_ms = int((time.time() - start) * 1000)
            return {"columns": columns, "rows": [list(r) for r in rows], "elapsed_ms": elapsed_ms}
        finally:
            try:
                if conn:
                    conn.close()
            except Exception:
                pass
