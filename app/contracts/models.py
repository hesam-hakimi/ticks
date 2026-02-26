"""app.contracts.models

Shared models for UI, orchestrator, agents, and tools.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Literal, Optional

Intent = Literal["DATA_QA", "ANALYTICS_REPORT", "GENERAL_QA", "OUT_OF_SCOPE"]
Backend = Literal["sqlserver", "sqlite"]


@dataclass
class UISettings:
    """UI-configurable runtime controls."""
    debug: bool
    max_rows_ui: int
    max_cols_ui: int
    max_exec_seconds: int
    backend: Backend


@dataclass
class ChatRequest:
    """Incoming chat request from UI."""
    session_id: str
    message: str
    ui: UISettings
    history: list[dict[str, str]]  # [{"role":"user|assistant","content":"..."}]


@dataclass
class Citation:
    """Reference to a retrieved metadata document."""
    source: Literal["field", "table", "relationship"]
    doc_id: str
    snippet: str
    schema_name: Optional[str] = None
    table_name: Optional[str] = None
    column_name: Optional[str] = None


@dataclass
class GroundingPack:
    """Retrieved docs + citations passed to downstream steps."""
    citations: list[Citation]
    raw_docs: dict[str, list[dict[str, Any]]]
    grounding_text: str


@dataclass
class ClarificationResult:
    """Outcome of clarity check step."""
    is_clear: bool
    questions: list[str]
    assumptions_if_proceed: list[str]


@dataclass
class SqlPlan:
    """SQL in two dialects."""
    sql_server: str
    sql_sqlite: str
    used_tables: list[str]
    notes: str


@dataclass
class SafetyReport:
    """Safety decision about SQL."""
    is_safe: bool
    safe_sql_server: Optional[str]
    safe_sql_sqlite: Optional[str]
    violations: list[str]
    user_message: Optional[str]


@dataclass
class QueryResult:
    """Limited preview of query results."""
    columns: list[str]
    rows: list[list[Any]]
    row_count_returned: int
    truncated: bool
    elapsed_ms: int


@dataclass
class ChartSpec:
    """Chart instructions for analytics."""
    chart_type: Literal["line", "bar", "pie", "none"]
    x: Optional[str] = None
    y: Optional[str] = None
    title: Optional[str] = None


@dataclass
class StepTrace:
    """A single step trace for debug mode."""
    step_name: str
    payload: dict[str, Any]


@dataclass
class ChatResponse:
    """Final response from orchestrator."""
    status: Literal["ok", "need_clarification", "blocked", "error"]
    answer: str
    followups: list[str]
    citations: list[Citation]
    sql_server: Optional[str] = None
    sql_sqlite: Optional[str] = None
    result: Optional[QueryResult] = None
    chart_spec: Optional[ChartSpec] = None
    traces: list[StepTrace] | None = None
    clarifying_questions: list[str] | None = None
    # Analytics report blocks (each block includes a small aggregated table + chart spec)
    report_blocks: list[dict[str, Any]] | None = None


@dataclass
class ReportChart:
    """Chart instructions from planner."""
    library: Literal["plotly", "seaborn", "none"]
    type: Literal["line", "bar", "pie", "table", "none"]
    x: Optional[str] = None
    y: Optional[str] = None
    title: Optional[str] = None


@dataclass
class ReportQuerySpec:
    """A single query in an analytics report plan."""
    name: str
    purpose: str
    sql_server: str
    sql_sqlite: str
    chart: ReportChart


@dataclass
class ReportPlan:
    """Analytics report plan with multiple aggregated queries."""
    title: str
    summary: str
    queries: list[ReportQuerySpec]
    followups: list[str]


@dataclass
class ReportArtifact:
    """Final report artifact returned to UI."""
    markdown: str
    charts: list[Any]
    tables: list[Any]
