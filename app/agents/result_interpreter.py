"""app.agents.result_interpreter

Produces a business-friendly answer from limited result preview.
"""

from __future__ import annotations
from app.contracts.agent_base import BaseAgent, ChatContext


def _format_preview(columns, rows, max_chars: int = 12000) -> str:
    lines = ["\t".join(columns)]
    for r in rows[:50]:
        lines.append("\t".join(["" if v is None else str(v) for v in r]))
    txt = "\n".join(lines)
    return txt[:max_chars]


class ResultInterpreterAgent(BaseAgent[dict]):
    name = "result_interpreter"

    def __init__(self, llm_tool, tracer, logger):
        self.llm = llm_tool
        self.tracer = tracer
        self.logger = logger

    def run(self, ctx: ChatContext) -> dict:
        qr = ctx.query_result
        sql = ctx.safety.safe_sql_server if ctx.request.ui.backend == "sqlserver" else ctx.safety.safe_sql_sqlite
        preview = _format_preview(qr.columns, qr.rows) if qr else "(no results)"
        out = self.llm.interpret_result(ctx.request.message, sql or "", preview, ctx.request.history)
        self.tracer.add(self.name, {"followups": out.get("followups", [])})
        return out
