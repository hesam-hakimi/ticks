"""app.agents.sql_safety_guard

Validates SQL policy and applies row limits.
"""

from __future__ import annotations
from app.contracts.agent_base import BaseAgent, ChatContext
from app.contracts.models import SafetyReport


class SQLSafetyGuardAgent(BaseAgent[SafetyReport]):
    name = "sql_safety_guard"

    def __init__(self, sql_policy, limits_policy, tracer, logger):
        self.sql_policy = sql_policy
        self.limits = limits_policy
        self.tracer = tracer
        self.logger = logger

    def run(self, ctx: ChatContext) -> SafetyReport:
        plan = ctx.sql_plan
        if plan is None:
            rep = SafetyReport(False, None, None, ["No SQL plan"], "Unable to create a safe query.")
            self.tracer.add(self.name, {"is_safe": False, "violations": rep.violations})
            return rep

        backend = ctx.request.ui.backend
        sql = plan.sql_server if backend == "sqlserver" else plan.sql_sqlite

        violations = self.sql_policy.validate(sql)
        if violations:
            rep = SafetyReport(
                is_safe=False,
                safe_sql_server=None,
                safe_sql_sqlite=None,
                violations=violations,
                user_message="Your request would require an unsafe query. Please rephrase as a read-only analysis question.",
            )
            self.tracer.add(self.name, {"is_safe": False, "violations": violations})
            return rep

        safe_server = self.limits.apply_row_limit(plan.sql_server, "sqlserver", ctx.request.ui.max_rows_ui)
        safe_sqlite = self.limits.apply_row_limit(plan.sql_sqlite, "sqlite", ctx.request.ui.max_rows_ui)

        rep = SafetyReport(True, safe_server, safe_sqlite, [], None)
        self.tracer.add(self.name, {"is_safe": True})
        return rep
