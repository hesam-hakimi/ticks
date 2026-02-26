"""app.agents.db_executor

Executes the safe SQL on the chosen backend and truncates for UI.
"""

from __future__ import annotations
from app.contracts.agent_base import BaseAgent, ChatContext
from app.contracts.models import QueryResult
from app.errors import ToolError


class DBExecutorAgent(BaseAgent[QueryResult]):
    name = "db_executor"

    def __init__(self, db_tool, limits_policy, tracer, logger):
        self.db = db_tool
        self.limits = limits_policy
        self.tracer = tracer
        self.logger = logger

    def run(self, ctx: ChatContext) -> QueryResult:
        if not ctx.safety or not ctx.safety.is_safe:
            raise ToolError("Attempted to execute without safe SQL")

        sql = ctx.safety.safe_sql_server if ctx.request.ui.backend == "sqlserver" else ctx.safety.safe_sql_sqlite
        if not sql:
            raise ToolError("No SQL to execute")

        out = self.db.execute(sql, timeout_seconds=ctx.request.ui.max_exec_seconds)
        cols = list(out.get("columns", []))
        rows = list(out.get("rows", []))
        elapsed = int(out.get("elapsed_ms", 0))

        cols, rows, truncated = self.limits.truncate_result(cols, rows, ctx.request.ui.max_cols_ui, ctx.request.ui.max_rows_ui)

        res = QueryResult(
            columns=cols,
            rows=rows,
            row_count_returned=len(rows),
            truncated=bool(truncated),
            elapsed_ms=elapsed,
        )
        self.tracer.add(self.name, {"row_count": res.row_count_returned, "elapsed_ms": elapsed, "truncated": truncated})
        return res
