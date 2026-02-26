"""app.viz.chart_renderer

Chart rendering for analytics reports.

Requirements:
- Do not confine visualization to matplotlib.
- Prefer Plotly for interactive charts in Streamlit.
- Support Seaborn as an alternative for quick, neat statistical plots.

The planner can request a library preference in the chart spec.
"""

from __future__ import annotations
from typing import Any, Optional

import pandas as pd


def render_chart(df: pd.DataFrame, chart: dict[str, Any]) -> Any | None:
    """Render a chart and return an object suitable for Streamlit (plotly fig or matplotlib fig)."""
    if df is None or df.empty:
        return None

    lib = (chart.get("library") or "plotly").lower()
    ctype = (chart.get("type") or "none").lower()
    x = chart.get("x")
    y = chart.get("y")
    title = chart.get("title")

    if ctype in ("none",):
        return None

    # Plotly preferred
    if lib == "plotly":
        import plotly.express as px

        if ctype == "bar" and x and y and x in df.columns and y in df.columns:
            fig = px.bar(df, x=x, y=y, title=title)
            return fig
        if ctype == "line" and x and y and x in df.columns and y in df.columns:
            fig = px.line(df, x=x, y=y, title=title)
            return fig
        if ctype == "pie" and x and y and x in df.columns and y in df.columns:
            fig = px.pie(df, names=x, values=y, title=title)
            return fig
        # fallback: first two cols
        if len(df.columns) >= 2 and ctype in ("bar", "line"):
            fig = px.bar(df, x=df.columns[0], y=df.columns[1], title=title) if ctype == "bar" else px.line(df, x=df.columns[0], y=df.columns[1], title=title)
            return fig
        return None

    # Seaborn option
    if lib == "seaborn":
        import matplotlib.pyplot as plt
        import seaborn as sns

        fig = plt.figure()
        ax = fig.add_subplot(111)
        if ctype == "bar" and x and y and x in df.columns and y in df.columns:
            sns.barplot(data=df, x=x, y=y, ax=ax)
        elif ctype == "line" and x and y and x in df.columns and y in df.columns:
            sns.lineplot(data=df, x=x, y=y, ax=ax)
        else:
            # basic fallback
            if len(df.columns) >= 2:
                sns.barplot(data=df, x=df.columns[0], y=df.columns[1], ax=ax)
            else:
                return None

        if title:
            ax.set_title(title)
        fig.tight_layout()
        return fig

    return None
