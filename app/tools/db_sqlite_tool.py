"""app.tools.db_sqlite_tool

SQLite execution tool (testing/dev).
"""

from __future__ import annotations
import sqlite3
import time
from typing import Any


class SqliteDatabaseTool:
    """SQLite execution wrapper."""

    def __init__(self, sqlite_path: str, logger):
        self.sqlite_path = sqlite_path
        self.logger = logger

    def execute(self, sql: str, timeout_seconds: int) -> dict[str, Any]:
        start = time.time()
        conn = sqlite3.connect(self.sqlite_path, timeout=timeout_seconds)
        try:
            cur = conn.cursor()
            cur.execute(sql)
            columns = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall() if cur.description else []
            elapsed_ms = int((time.time() - start) * 1000)
            return {"columns": columns, "rows": [list(r) for r in rows], "elapsed_ms": elapsed_ms}
        finally:
            conn.close()
