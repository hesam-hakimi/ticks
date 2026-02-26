"""app.agents.error_triage

Lets the model decide whether to retry/clarify/stop based on DB error.
"""

from __future__ import annotations
from app.contracts.agent_base import BaseAgent, ChatContext


class ErrorTriageAgent(BaseAgent[dict]):
    name = "error_triage"

    def __init__(self, llm_tool, tracer, logger):
        self.llm = llm_tool
        self.tracer = tracer
        self.logger = logger

    def run(self, ctx: ChatContext) -> dict:
        grounding = ctx.grounding.grounding_text if ctx.grounding else ""
        sql = ""
        if ctx.safety and ctx.safety.is_safe:
            sql = ctx.safety.safe_sql_server if ctx.request.ui.backend == "sqlserver" else (ctx.safety.safe_sql_sqlite or "")
        out = self.llm.triage_error(ctx.request.message, sql, ctx.last_error or "", grounding, ctx.request.history)
        self.tracer.add(self.name, out)
        return out
