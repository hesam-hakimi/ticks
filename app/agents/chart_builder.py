"""app.agents.chart_builder

Phase 2: render charts from aggregated results only.
"""

from __future__ import annotations
from typing import Optional
import matplotlib.pyplot as plt


def render_chart(result, chart_spec) -> Optional[plt.Figure]:
    """Render a chart from a QueryResult and ChartSpec. Returns a matplotlib Figure or None."""
    if not result or not chart_spec or chart_spec.chart_type == "none":
        return None
    if not result.columns or not result.rows:
        return None

    cols = result.columns
    x_col = chart_spec.x if chart_spec.x in cols else cols[0]
    y_col = chart_spec.y if chart_spec.y in cols else (cols[1] if len(cols) > 1 else None)
    if y_col is None:
        return None

    xi = cols.index(x_col)
    yi = cols.index(y_col)

    x = [r[xi] for r in result.rows]
    y = [r[yi] for r in result.rows]

    fig = plt.figure()
    ax = fig.add_subplot(111)

    if chart_spec.chart_type == "line":
        ax.plot(x, y)
    elif chart_spec.chart_type == "bar":
        ax.bar(x, y)
    elif chart_spec.chart_type == "pie":
        ax.pie(y, labels=[str(v) for v in x])
    else:
        return None

    if chart_spec.title:
        ax.set_title(chart_spec.title)

    if chart_spec.chart_type in ("line", "bar"):
        ax.set_xlabel(str(x_col))
        ax.set_ylabel(str(y_col))

    fig.tight_layout()
    return fig
