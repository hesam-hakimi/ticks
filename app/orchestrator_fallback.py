"""app.orchestrator

FallbackOrchestrator (code) with guardrails + first-class AutoGen agents.

Best-practice features implemented:
- Deterministic guardrails: SELECT-only policy, row/col/time limits, max retry attempts, truncation
- Two execution paths:
    (A) DATA_QA: single query answer
    (B) ANALYTICS_REPORT: multi-query report plan -> execute -> charts -> markdown report
- FastPath for common queries can be reintroduced; for now keep this version focused on robust reporting.

NOTE:
- Agents are single-turn and must return strict JSON.
- The orchestrator owns the tools (AI Search, DB) and enforces policy.
"""

from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any

from app.contracts.agent_base import ChatContext
from app.fastpath.query_registry import default_registry, extract_params, render_template
from app.fastpath.matcher import best_match

from app.contracts.models import (
    ChatRequest, ChatResponse, StepTrace, ChartSpec,
    SqlPlan, ReportPlan, ReportQuerySpec, ReportChart
)


@dataclass
class FallbackOrchestrator:
    agent_manager: Any  # AgentManager
    metadata_retriever: Any
    sql_safety: Any
    db_executor: Any
    llm_tool: Any  # AzureOpenAITool (still used for small utilities like chart spec if needed)
    tracer: Any
    logger: Any
    max_retry_attempts: int = 5

    def _trace(self, step: str, payload: Any) -> None:
        try:
            self.tracer.add(step, payload)
        except Exception:
            pass

    def _preview_text(self, columns: list[str], rows: list[list[Any]], max_rows: int = 50) -> str:
        lines = ["\t".join(columns)]
        for r in rows[:max_rows]:
            lines.append("\t".join(["" if v is None else str(v) for v in r]))
        return "\n".join(lines)

    def run(self, req: ChatRequest) -> ChatResponse:
        ctx = ChatContext(request=req)

        # 1) Intent
        r = self.agent_manager.call_json(self.agent_manager.intent_router, {"user_text": req.message})
        intent_obj = r.json_obj or {"intent": "DATA_QA"}
        intent = intent_obj.get("intent", "DATA_QA")
        self._trace("intent_router", intent_obj)
        ctx.intent = intent

        # 2) Retrieval grounding
        ctx.grounding = self.metadata_retriever.run(ctx)

        # 3) Clarity check (single-turn)
        c = self.agent_manager.call_json(
            self.agent_manager.requirement_clarity,
            {"user_text": req.message, "grounding": ctx.grounding.grounding_text if ctx.grounding else ""},
        )
        clarity = c.json_obj or {"is_clear": True}
        self._trace("requirement_clarity", clarity)
        if not bool(clarity.get("is_clear", True)):
            return ChatResponse(
                status="need_clarification",
                answer="I need a bit more detail before I can query the data.",
                followups=[],
                citations=ctx.grounding.citations if ctx.grounding else [],
                traces=[StepTrace(t["step"], t["payload"]) for t in self.tracer.traces] if req.ui.debug else None,
                clarifying_questions=list(clarity.get("questions", []))[:5],
            )

        # ---------- ANALYTICS_REPORT path ----------
        if intent == "ANALYTICS_REPORT":
            plan_res = self.agent_manager.call_json(
                self.agent_manager.report_planner,
                {"user_text": req.message, "grounding": ctx.grounding.grounding_text if ctx.grounding else ""},
            )
            plan_obj = plan_res.json_obj or {}
            self._trace("report_planner", plan_obj)

            # Parse plan safely
            title = str(plan_obj.get("title", "Analytics Report"))
            summary = str(plan_obj.get("summary", ""))
            qlist = plan_obj.get("queries", []) or []
            followups = list(plan_obj.get("followups", []))[:5]

            query_specs: list[ReportQuerySpec] = []
            for q in qlist[:5]:
                chart = q.get("chart", {}) or {}
                query_specs.append(
                    ReportQuerySpec(
                        name=str(q.get("name", "query")),
                        purpose=str(q.get("purpose", "")),
                        sql_server=str(q.get("sql_server", "")),
                        sql_sqlite=str(q.get("sql_sqlite", "")),
                        chart=ReportChart(
                            library=(chart.get("library") or "plotly"),
                            type=(chart.get("type") or "none"),
                            x=chart.get("x"),
                            y=chart.get("y"),
                            title=chart.get("title"),
                        ),
                    )
                )

            # Execute each query with safety and guardrails
            executed = []
            for spec in query_specs:
                ctx.sql_plan = SqlPlan(
                    sql_server=spec.sql_server,
                    sql_sqlite=spec.sql_sqlite,
                    used_tables=[],
                    notes=f"Report query: {spec.name} - {spec.purpose}",
                )
                ctx.safety = self.sql_safety.run(ctx)
                if not ctx.safety.is_safe:
                    executed.append({"name": spec.name, "error": "Blocked by SQL policy", "preview": ""})
                    continue

                # Retry loop (LLM triage allowed, but bounded)
                attempt = 0
                while True:
                    try:
                        ctx.query_result = self.db_executor.run(ctx)
                        preview = self._preview_text(ctx.query_result.columns, ctx.query_result.rows)
                        executed.append({
                            "name": spec.name,
                            "purpose": spec.purpose,
                            "chart": (viz if isinstance(viz, dict) else spec.chart.__dict__),
                                "fig": fig_obj,
                                "viz_description": (viz.get("description") if isinstance(viz, dict) else ""),
                                "alt_text": (viz.get("alt_text") if isinstance(viz, dict) else ""),
                            "columns": ctx.query_result.columns,
                            "rows": ctx.query_result.rows,
                            "preview": preview,
                            "sql_used": ctx.safety.safe_sql_server if req.ui.backend == "sqlserver" else ctx.safety.safe_sql_sqlite,
                        })
                        break
                    except Exception as e:
                        attempt += 1
                        if attempt >= self.max_retry_attempts:
                            executed.append({"name": spec.name, "error": str(e), "preview": ""})
                            break

                        sql_used = ctx.safety.safe_sql_server if req.ui.backend == "sqlserver" else (ctx.safety.safe_sql_sqlite or "")
                        triage = self.agent_manager.call_json(
                            self.agent_manager.error_triage,
                            {
                                "user_text": req.message,
                                "sql": sql_used,
                                "error": str(e),
                                "grounding": ctx.grounding.grounding_text if ctx.grounding else "",
                            },
                        ).json_obj or {"action": "STOP"}
                        self._trace("error_triage", triage)
                        action = triage.get("action", "STOP")
                        if action == "RETRY_WITH_PATCH":
                            # patch SQL and re-validate safety
                            if triage.get("patched_sql_server"):
                                ctx.sql_plan.sql_server = triage["patched_sql_server"]
                            if triage.get("patched_sql_sqlite"):
                                ctx.sql_plan.sql_sqlite = triage["patched_sql_sqlite"]
                            ctx.safety = self.sql_safety.run(ctx)
                            if not ctx.safety.is_safe:
                                executed.append({"name": spec.name, "error": "Patched SQL blocked by policy", "preview": ""})
                                break
                            continue
                        elif action == "ASK_CLARIFICATION":
                            return ChatResponse(
                                status="need_clarification",
                                answer=triage.get("user_message", "I need more detail."),
                                followups=[],
                                citations=ctx.grounding.citations if ctx.grounding else [],
                                traces=[StepTrace(t["step"], t["payload"]) for t in self.tracer.traces] if req.ui.debug else None,
                                clarifying_questions=list(triage.get("clarifying_questions", []))[:5],
                            )
                        else:
                            executed.append({"name": spec.name, "error": str(e), "preview": ""})
                            break

            # Report writer (markdown)
            # Provide only previews + small tables (bounded)
            summary_payload = {
                "title": title,
                "summary": summary,
                "executed": [
                    {
                        "name": x.get("name"),
                        "purpose": x.get("purpose", ""),
                        "preview": x.get("preview", "")[:8000],
                        "chart": x.get("chart", {}),
                    }
                    for x in executed
                ],
            }
            rep = self.agent_manager.call_json(self.agent_manager.report_writer, {"user_text": req.message, "summary": json.dumps(summary_payload)})
            rep_obj = rep.json_obj or {"markdown": f"# {title}\n\n{summary}", "followups": followups}
            self._trace("report_writer", rep_obj)

            # Return answer as markdown (UI will render)
            return ChatResponse(
                status="ok",
                answer=rep_obj.get("markdown", ""),
                followups=list(rep_obj.get("followups", []))[:5],
                citations=ctx.grounding.citations if ctx.grounding else [],
                traces=[StepTrace(t["step"], t["payload"]) for t in self.tracer.traces] if req.ui.debug else None,
                # Attach executed report data for UI rendering (use ChatResponse.result for first query only; UI will use traces for report data)
            )

        # ---------- DATA_QA path ----------
        limits = {
            "max_rows_ui": req.ui.max_rows_ui,
            "max_cols_ui": req.ui.max_cols_ui,
            "max_exec_seconds": req.ui.max_exec_seconds,
            "backend": req.ui.backend,
        }
        s = self.agent_manager.call_json(
            self.agent_manager.sql_generator,
            {"user_text": req.message, "grounding": ctx.grounding.grounding_text if ctx.grounding else "", "limits": limits},
        )
        sql_obj = s.json_obj or {}
        self._trace("sql_generator", {"notes": sql_obj.get("notes"), "used_tables": sql_obj.get("used_tables", [])})
        ctx.sql_plan = SqlPlan(
            sql_server=str(sql_obj.get("sql_server", "")),
            sql_sqlite=str(sql_obj.get("sql_sqlite", "")),
            used_tables=list(sql_obj.get("used_tables", [])),
            notes=str(sql_obj.get("notes", "")),
        )

        ctx.safety = self.sql_safety.run(ctx)
        if not ctx.safety.is_safe:
            return ChatResponse(
                status="blocked",
                answer=ctx.safety.user_message or "Blocked by SQL safety policy.",
                followups=[],
                citations=ctx.grounding.citations if ctx.grounding else [],
                traces=[StepTrace(t["step"], t["payload"]) for t in self.tracer.traces] if req.ui.debug else None,
            )

        # Execute with bounded retries
        attempt = 0
        while True:
            try:
                ctx.query_result = self.db_executor.run(ctx)
                break
            except Exception as e:
                attempt += 1
                if attempt >= self.max_retry_attempts:
                    return ChatResponse(
                        status="error",
                        answer=f"Query failed after {self.max_retry_attempts} attempts: {e}",
                        followups=[],
                        citations=ctx.grounding.citations if ctx.grounding else [],
                        traces=[StepTrace(t["step"], t["payload"]) for t in self.tracer.traces] if req.ui.debug else None,
                    )

                sql_used = ctx.safety.safe_sql_server if req.ui.backend == "sqlserver" else (ctx.safety.safe_sql_sqlite or "")
                triage = self.agent_manager.call_json(
                    self.agent_manager.error_triage,
                    {"user_text": req.message, "sql": sql_used, "error": str(e), "grounding": ctx.grounding.grounding_text if ctx.grounding else ""},
                ).json_obj or {"action": "STOP"}
                self._trace("error_triage", triage)
                action = triage.get("action", "STOP")
                if action == "RETRY_WITH_PATCH":
                    if triage.get("patched_sql_server"):
                        ctx.sql_plan.sql_server = triage["patched_sql_server"]
                    if triage.get("patched_sql_sqlite"):
                        ctx.sql_plan.sql_sqlite = triage["patched_sql_sqlite"]
                    ctx.safety = self.sql_safety.run(ctx)
                    if not ctx.safety.is_safe:
                        return ChatResponse(
                            status="blocked",
                            answer="Patched SQL blocked by policy.",
                            followups=[],
                            citations=ctx.grounding.citations if ctx.grounding else [],
                            traces=[StepTrace(t["step"], t["payload"]) for t in self.tracer.traces] if req.ui.debug else None,
                        )
                    continue
                elif action == "ASK_CLARIFICATION":
                    return ChatResponse(
                        status="need_clarification",
                        answer=triage.get("user_message", "I need more detail."),
                        followups=[],
                        citations=ctx.grounding.citations if ctx.grounding else [],
                        traces=[StepTrace(t["step"], t["payload"]) for t in self.tracer.traces] if req.ui.debug else None,
                        clarifying_questions=list(triage.get("clarifying_questions", []))[:5],
                    )
                else:
                    return ChatResponse(
                        status="error",
                        answer=triage.get("user_message", f"Query failed: {e}"),
                        followups=[],
                        citations=ctx.grounding.citations if ctx.grounding else [],
                        traces=[StepTrace(t["step"], t["payload"]) for t in self.tracer.traces] if req.ui.debug else None,
                    )

        preview = self._preview_text(ctx.query_result.columns, ctx.query_result.rows)
        interp_payload = {"user_text": req.message, "sql": (ctx.safety.safe_sql_server if req.ui.backend == "sqlserver" else ctx.safety.safe_sql_sqlite), "result_preview": preview}
        # Reuse report_writer agent for concise markdown? Here we keep plain answer using AzureOpenAITool interpret_result to avoid overkill.
        out = self.llm_tool.interpret_result(req.message, interp_payload["sql"] or "", preview, req.history)
        answer = str(out.get("answer", "")).strip() or "(no answer)"
        followups = list(out.get("followups", []))[:5]
        self._trace("interpret_result", {"followups": followups})

        return ChatResponse(
            status="ok",
            answer=answer,
            followups=followups,
            citations=ctx.grounding.citations if ctx.grounding else [],
            sql_server=ctx.safety.safe_sql_server,
            sql_sqlite=ctx.safety.safe_sql_sqlite,
            result=ctx.query_result,
            traces=[StepTrace(t["step"], t["payload"]) for t in self.tracer.traces] if req.ui.debug else None,
        )
