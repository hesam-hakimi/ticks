"""app.agents.sql_generator

Generates SQL (SQL Server + SQLite) based on grounding.
"""

from __future__ import annotations
from app.contracts.agent_base import BaseAgent, ChatContext
from app.contracts.models import SqlPlan


class SQLGeneratorAgent(BaseAgent[SqlPlan]):
    name = "sql_generator"

    def __init__(self, llm_tool, tracer, logger):
        self.llm = llm_tool
        self.tracer = tracer
        self.logger = logger

    def run(self, ctx: ChatContext) -> SqlPlan:
        grounding = ctx.grounding.grounding_text if ctx.grounding else ""
        limits = {
            "max_rows_ui": ctx.request.ui.max_rows_ui,
            "max_cols_ui": ctx.request.ui.max_cols_ui,
            "max_exec_seconds": ctx.request.ui.max_exec_seconds,
            "backend": ctx.request.ui.backend,
        }
        out = self.llm.generate_sql(ctx.request.message, grounding, limits, ctx.request.history)
        self.tracer.add(self.name, {"notes": out.get("notes"), "used_tables": out.get("used_tables", [])})
        return SqlPlan(
            sql_server=str(out.get("sql_server", "")),
            sql_sqlite=str(out.get("sql_sqlite", "")),
            used_tables=list(out.get("used_tables", [])),
            notes=str(out.get("notes", "")),
        )
