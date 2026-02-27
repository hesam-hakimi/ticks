"""app.orchestrator

Primary orchestrator implementing the new "currently available data first" flow.

Goals:
- Answer from in-memory summarized datasets (fast, no SQL latency).
- If data is not available, ask the user if they want to search elsewhere.
- Handle greetings and out-of-scope questions gracefully.
- Support on-demand visualizations even when not specified in the intent registry.

Fallback:
- If user confirms, route to the existing SQL/RAG pipeline (FallbackOrchestrator).
"""

from __future__ import annotations

import re
import json
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Optional

import pandas as pd

from app.contracts.models import ChatRequest, ChatResponse, StepTrace
from app.available_data.store import AvailableDataStore
from app.available_data.registry import load_intent_registry, load_built_in_questions
from app.available_data.engine import AvailableDataEngine
from app.viz.code_sandbox import run_viz_code
from app.viz.chart_renderer import render_chart

from app.orchestrator_fallback import FallbackOrchestrator


_GREETINGS = {
    "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
    "morning", "afternoon", "evening"
}


def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _is_greeting(text: str) -> bool:
    t = text.strip().lower()
    if t in _GREETINGS:
        return True
    # short greeting phrases
    if len(t) <= 20 and any(g in t for g in ["hi", "hello", "good morning", "good evening"]):
        return True
    return False


def _role_from_req(req: ChatRequest) -> str:
    meta = req.meta or {}
    role = str(meta.get("role") or "CEO").strip().upper()
    return role if role in ("CEO", "CFO", "CTO") else "CEO"


def _selected_intent(req: ChatRequest) -> Optional[str]:
    meta = req.meta or {}
    v = meta.get("selected_intent")
    return str(v) if v else None


def _confirm_search_elsewhere(req: ChatRequest) -> bool:
    meta = req.meta or {}
    return bool(meta.get("confirm_search_elsewhere", False))


def _extract_branch_token(text: str) -> Optional[str]:
    t = (text or "").strip()
    if not t:
        return None
    m = re.search(r"\b([A-Za-z]{2,})\s+branch\b", t, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m2 = re.search(r"\bbranch\s+([A-Za-z0-9_-]{2,})\b", t, flags=re.IGNORECASE)
    if m2:
        return m2.group(1).strip()
    return None


def _is_trend_request(text: str) -> bool:
    t = (text or "").lower()
    keys = ("trend", "forecast", "predict", "projection", "next month", "next two month", "next 2 month")
    return any(k in t for k in keys)


def _cap_df(df: pd.DataFrame, max_rows: int, max_cols: int, time_col: Optional[str] = None, preserve_recent: bool = False) -> pd.DataFrame:
    cols = list(df.columns)[:max_cols]
    d = df[cols]
    if preserve_recent and time_col and time_col in d.columns:
        return d.tail(max_rows).copy()
    return d.head(max_rows).copy()


def _forecast_next_months(
    df: pd.DataFrame,
    time_col: Optional[str],
    metric_cols: list[str],
    periods: int = 2,
) -> tuple[pd.DataFrame, list[str]]:
    if df is None or df.empty or not time_col or time_col not in df.columns or periods <= 0:
        return df, []
    if "month" not in time_col.lower():
        return df, []

    dd = df.copy()
    dd[time_col] = pd.to_datetime(dd[time_col], errors="coerce")
    dd = dd.dropna(subset=[time_col]).sort_values(time_col)
    if dd.empty:
        return df, []

    usable_metrics = [
        c for c in metric_cols
        if c in dd.columns and pd.api.types.is_numeric_dtype(dd[c]) and c not in ("lat", "lon")
    ]
    if not usable_metrics:
        return dd, []

    group_cols = [
        c for c in dd.columns
        if c not in usable_metrics and c != time_col and not pd.api.types.is_numeric_dtype(dd[c])
    ]

    forecast_rows: list[dict[str, Any]] = []
    grouped = dd.groupby(group_cols, dropna=False) if group_cols else [((), dd)]
    for gkey, gdf in grouped:
        hist = gdf[[time_col] + usable_metrics].groupby(time_col, as_index=False).mean().sort_values(time_col)
        if hist.empty:
            continue
        last_time = hist[time_col].iloc[-1]

        base_vals: dict[str, float] = {}
        slopes: dict[str, float] = {}
        for m in usable_metrics:
            y = pd.to_numeric(hist[m], errors="coerce").dropna()
            if y.empty:
                continue
            y_tail = y.tail(min(6, len(y)))
            base_vals[m] = float(y_tail.iloc[-1])
            if len(y_tail) >= 2:
                slopes[m] = float(y_tail.iloc[-1] - y_tail.iloc[0]) / float(len(y_tail) - 1)
            else:
                slopes[m] = 0.0

        if not base_vals:
            continue

        group_map: dict[str, Any] = {}
        if group_cols:
            if not isinstance(gkey, tuple):
                gkey = (gkey,)
            group_map = {col: val for col, val in zip(group_cols, gkey)}

        for step in range(1, periods + 1):
            row: dict[str, Any] = {time_col: last_time + pd.DateOffset(months=step), "__is_forecast": True}
            row.update(group_map)
            for m, base in base_vals.items():
                pred = base + slopes.get(m, 0.0) * step
                ml = m.lower()
                if any(k in ml for k in ("rate", "pct", "ratio")):
                    pred = max(0.0, min(1.0, pred))
                row[m] = float(pred)
            forecast_rows.append(row)

    if not forecast_rows:
        return dd, []

    out = pd.concat([dd, pd.DataFrame(forecast_rows)], ignore_index=True, sort=False)
    out = out.sort_values(time_col)
    if "__is_forecast" not in out.columns:
        out["__is_forecast"] = False
    out["__is_forecast"] = out["__is_forecast"].where(out["__is_forecast"].notna(), False).astype(bool)
    return out, usable_metrics


def _basic_key_numbers(df: pd.DataFrame, time_col: Optional[str]) -> list[dict[str, Any]]:
    """Extract simple key numbers from the latest row."""
    if df.empty:
        return []
    d = df.copy()
    latest = d.tail(1).iloc[0].to_dict()
    out = []
    for k, v in latest.items():
        if k == time_col:
            continue
        if k.startswith("__"):
            continue
        if isinstance(v, (int, float)) and not isinstance(v, bool) and k not in ("lat", "lon"):
            out.append({"metric": k, "value": float(v)})
    # keep top 8 by absolute value (roughly prioritizes big metrics)
    out.sort(key=lambda x: abs(x["value"]), reverse=True)
    return out[:8]


def _basic_observations(df: pd.DataFrame, time_col: Optional[str], metric_cols: list[str]) -> list[str]:
    obs = []
    if not time_col or df.empty:
        return obs
    d = df.copy()
    try:
        d[time_col] = pd.to_datetime(d[time_col], errors="coerce")
        d = d.sort_values(time_col)
    except Exception:
        pass

    # For up to 2 metrics, compare last vs first point in current window
    for m in metric_cols[:2]:
        if m not in d.columns or not pd.api.types.is_numeric_dtype(d[m]):
            continue
        first = float(d[m].iloc[0])
        last = float(d[m].iloc[-1])
        if first == 0:
            continue
        pct = (last - first) / abs(first)
        direction = "increased" if pct >= 0 else "decreased"
        obs.append(f"{m} {direction} by {pct:.1%} over the selected period.")
    return obs


@dataclass
class Orchestrator:
    agent_manager: Any
    tracer: Any
    logger: Any
    fallback: FallbackOrchestrator

    def _trace(self, step: str, payload: dict[str, Any]) -> None:
        try:
            self.tracer.add(step, payload)
        except Exception:
            pass

    def _ask_search_elsewhere(self) -> ChatResponse:
        return ChatResponse(
            status="need_confirmation",
            answer="I can’t find that data in what’s currently available. Do you want me to search elsewhere?",
            followups=[],
            citations=[],
        )

    def run(self, req: ChatRequest) -> ChatResponse:
        role = _role_from_req(req)
        intent_key = _selected_intent(req)
        self._trace("meta", {"role": role, "selected_intent": intent_key, "confirm_search_elsewhere": _confirm_search_elsewhere(req)})

        # Greetings
        if _is_greeting(req.message):
            return ChatResponse(
                status="ok",
                answer=(
                    "Hello. Select a role to see recommended questions, or ask a question about trends, performance, risk, or platform health."
                ),
                followups=[
                    "Show revenue and net income trend over the last 12 months",
                    "Show branch map: deposits and risk score",
                    "Show tech reliability trend: uptime, incidents, latency",
                ],
                citations=[],
            )

        # If user confirmed fallback, route to existing pipeline
        if _confirm_search_elsewhere(req):
            self._trace("routing", {"path": "fallback"})
            resp = self.fallback.run(req)
            return resp

        # Load registry + store
        registry = load_intent_registry()
        built_in = load_built_in_questions()
        store = AvailableDataStore()
        engine = AvailableDataEngine(store, registry)

        # Determine intent if not set
        if not intent_key:
            msg_lower = req.message.lower()
            if "branch" in msg_lower and "branch_geo_map" in registry.keys():
                intent_key = "branch_geo_map"
                self._trace("intent_match", {"method": "rule_branch", "intent_key": intent_key})

            # try fuzzy match built-in questions first
            if not intent_key:
                best = None
                for q in built_in:
                    s = _sim(req.message, q.text)
                    if (best is None) or (s > best[0]):
                        best = (s, q.intent)
                if best and best[0] >= 0.86:
                    intent_key = best[1]
                    self._trace("intent_match", {"method": "fuzzy_builtin", "intent_key": intent_key, "score": best[0]})
                else:
                    # ask registry_router agent to pick best intent
                    payload = {
                        "role": role,
                        "question": req.message,
                        "intent_keys": registry.keys()[:200],
                        "built_in_questions": [q.text for q in built_in if role in [r.upper() for r in q.roles]][:50],
                    }
                    rr = self.agent_manager.call_json(self.agent_manager.registry_router, payload)
                    obj = rr.json_obj or {}
                    picked = str(obj.get("intent_key", "NONE"))
                    conf = float(obj.get("confidence", 0.0) or 0.0)
                    self._trace("registry_router", {"picked": picked, "confidence": conf, "reason": obj.get("reason", "")})
                    if picked and picked != "NONE" and picked in registry.keys():
                        intent_key = picked

        # Attempt available-data answer
        if intent_key:
            ans = engine.answer_from_intent(intent_key, req.message)
            self._trace("available_data.intent", {"intent_key": intent_key, "ok": ans.ok, "reason": ans.reason, "dataset": ans.dataset})
        else:
            ans = engine.answer_from_free_question(req.message)
            self._trace("available_data.free", {"ok": ans.ok, "reason": ans.reason, "dataset": ans.dataset})

        if not ans.ok or ans.df is None:
            # We did not find the data in currently available datasets.
            resp = self._ask_search_elsewhere()
            resp.traces = [StepTrace(t["step"], t["payload"]) for t in self.tracer.traces] if req.ui.debug else None
            return resp

        add_forecast = _is_trend_request(req.message)
        df_work = ans.df.copy()

        if "branch" in req.message.lower():
            token = _extract_branch_token(req.message)
            if token:
                mask = pd.Series(False, index=df_work.index)
                for col in ("branch_name", "city", "state", "region"):
                    if col in df_work.columns:
                        mask = mask | df_work[col].astype(str).str.contains(token, case=False, na=False)
                filtered = df_work[mask].copy()
                self._trace("branch_filter", {"token": token, "rows_before": len(df_work), "rows_after": len(filtered)})
                if filtered.empty:
                    return ChatResponse(
                        status="ok",
                        answer=f"No data available for {token} branch in currently available datasets.",
                        followups=[
                            "Show branch map: deposits and risk score",
                            "Show branch stats for CA branch",
                            "Do you want me to search elsewhere?",
                        ],
                        citations=[],
                    )
                df_work = filtered

        forecast_metrics: list[str] = []
        if add_forecast:
            df_work, forecast_metrics = _forecast_next_months(df_work, ans.time_col, ans.metric_cols, periods=2)
            if forecast_metrics and "__is_forecast" in df_work.columns:
                self._trace("forecast", {"enabled": True, "months": 2, "metrics": forecast_metrics})

        # Cap output
        df = _cap_df(
            df_work,
            req.ui.max_rows_ui,
            req.ui.max_cols_ui,
            time_col=ans.time_col,
            preserve_recent=bool(forecast_metrics),
        )

        # On-demand visualization
        df_viz = df.copy()
        default_viz_hint: dict[str, Any] = {}
        if _is_trend_request(req.message) and ans.time_col and ans.time_col in df_viz.columns:
            y_metric = None
            for preferred in ("churn_rate", "churn_pct"):
                if preferred in df_viz.columns:
                    y_metric = preferred
                    break
            if y_metric is None:
                for m in ans.metric_cols:
                    if m in df_viz.columns and not m.startswith("__"):
                        y_metric = m
                        break

            color_col = None
            if "segment" in df_viz.columns and "channel" in df_viz.columns:
                df_viz["__series"] = df_viz["segment"].astype(str) + ", " + df_viz["channel"].astype(str)
                color_col = "__series"
            elif "segment" in df_viz.columns:
                color_col = "segment"
            elif "channel" in df_viz.columns:
                color_col = "channel"

            if y_metric:
                default_viz_hint = {
                    "library": "plotly",
                    "chart_type": "line",
                    "x": ans.time_col,
                    "y": y_metric,
                    "color": color_col,
                    "title": "Trend",
                }

        if default_viz_hint:
            vz = {
                **default_viz_hint,
                "description": "Deterministic trend chart using time on x-axis and churn metric on y-axis.",
                "alt_text": "Line chart showing churn trend over time split by segment/channel.",
            }
            self._trace("viz_coder", {"viz": "skipped_for_trend", "hint": vz})
        else:
            viz_payload = {
                "user_request": req.message,
                "constraints": {"prefer": "plotly", "no_imports": True, "timeout_seconds": 5},
                "table": {"columns": list(df_viz.columns), "rows": df_viz.head(60).to_dict(orient="records")},
            }
            vz = self.agent_manager.call_json(self.agent_manager.viz_coder, viz_payload).json_obj or {}
            self._trace("viz_coder", {"viz": vz})

        fig_obj = None
        viz_desc = ""
        alt_text = ""
        try:
            code = str(vz.get("code") or "")
            viz_desc = str(vz.get("description") or "")
            alt_text = str(vz.get("alt_text") or "")
            if code.strip():
                sr = run_viz_code(code, df_viz, timeout_seconds=5)
                if sr.ok:
                    fig_obj = sr.fig
                else:
                    self._trace("viz_sandbox_error", {"error": sr.error})
            if fig_obj is None:
                # fallback: simple renderer for line/bar/pie using hint fields if provided
                fig_obj = render_chart(df_viz, default_viz_hint or vz or {})
        except Exception as e:
            self._trace("viz_error", {"error": str(e)})

        # Writer agent (markdown)
        key_numbers = _basic_key_numbers(df, ans.time_col)
        observations = _basic_observations(df, ans.time_col, ans.metric_cols)
        if forecast_metrics:
            observations.append("Includes a 2-month forecast based on recent trend slope.")
        writer_payload = {
            "role": role,
            "question": req.message,
            "dataset": ans.dataset,
            "key_numbers": key_numbers,
            "observations": observations,
            "chart_descriptions": [viz_desc] if viz_desc else [],
        }
        wr = self.agent_manager.call_json(self.agent_manager.executive_writer, writer_payload)
        wobj = wr.json_obj or {}
        markdown = str(wobj.get("markdown") or "").strip()
        followups = list(wobj.get("followups") or [])[:5]
        if not markdown:
            # fallback markdown
            markdown = (
                f"# Briefing\n\n"
                f"Role: {role}\n\n"
                f"Question: {req.message}\n\n"
                f"Key numbers: {json.dumps(key_numbers, indent=2, default=str)}\n"
            )
        self._trace("executive_writer", {"followups": followups})

        resp = ChatResponse(
            status="ok",
            answer=markdown,
            followups=followups,
            citations=[],
            report_blocks=[
                {
                    "name": ans.dataset or "report",
                    "purpose": req.message,
                    "columns": list(df.columns),
                    "rows": df.values.tolist(),
                    "fig": fig_obj,
                    "viz_description": viz_desc,
                    "alt_text": alt_text,
                }
            ],
        )
        resp.traces = [StepTrace(t["step"], t["payload"]) for t in self.tracer.traces] if req.ui.debug else None
        return resp
