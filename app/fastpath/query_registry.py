"""app.fastpath.query_registry

Fast-path support for a library of common queries (e.g., ~100).

Strategy:
- Maintain a registry of parameterized SQL templates + simple match keywords.
- Extract parameters with regex and render SQL.
"""

from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Any


@dataclass(frozen=True)
class QueryTemplate:
    name: str
    intent: str
    keywords: list[str]
    param_patterns: dict[str, str]  # param -> regex with (?P<param>...)
    sql_server_template: str
    sql_sqlite_template: str
    description: str = ""


def extract_params(text: str, tmpl: QueryTemplate) -> dict[str, str]:
    params: dict[str, str] = {}
    for key, pattern in tmpl.param_patterns.items():
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m and key in m.groupdict():
            params[key] = m.group(key)
    return params


def render_template(template: str, params: dict[str, str]) -> str:
    out = template
    for k, v in params.items():
        out = out.replace("{" + k + "}", v)
    return out


def default_registry() -> list[QueryTemplate]:
    # Starter example(s). Replace with your real 'top ~100' library. Add templates with clear keywords + regex params; keep queries aggregated.
    return [
        QueryTemplate(
            name="deposit_count_by_day",
            intent="ANALYTICS_REPORT",
            keywords=["deposit", "count", "by day", "daily"],
            param_patterns={
                "src_cd": r"\b(?P<src_cd>IMSB|STAX)\b",
                "days": r"last\s+(?P<days>\d+)\s+days",
            },
            sql_server_template=(
                "SELECT TOP (50) RRDW_AS_OF_DT as day, COUNT(1) as deposit_count "
                "FROM rrdw_dlv.dlv_dep_tran "
                "WHERE RRDW_SRC_CD = '{src_cd}' AND RRDW_AS_OF_DT >= DATEADD(day, -{days}, CAST(GEcompany_nameATE() as date)) "
                "GROUP BY RRDW_AS_OF_DT ORDER BY RRDW_AS_OF_DT"
            ),
            sql_sqlite_template=(
                "SELECT RRDW_AS_OF_DT as day, COUNT(1) as deposit_count "
                "FROM dlv_dep_tran "
                "WHERE RRDW_SRC_CD = '{src_cd}' AND RRDW_AS_OF_DT >= date('now','-{days} day') "
                "GROUP BY RRDW_AS_OF_DT ORDER BY RRDW_AS_OF_DT LIMIT 50"
            ),
            description="Daily deposit counts for a source code over last N days.",
        )
    ]
