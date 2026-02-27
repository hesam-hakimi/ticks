"""app.viz.chart_renderer

Chart rendering utilities for Streamlit.

- Plotly is preferred (interactive).
- Seaborn/Matplotlib is supported as a fallback.

This renderer is used both for:
- Registry-defined chart hints
- LLM-generated chart hints (when code execution is not provided)
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def render_chart(df: pd.DataFrame, chart: dict[str, Any]) -> Any | None:
    """Render a chart and return a Plotly or Matplotlib figure."""
    if df is None or df.empty or not isinstance(chart, dict):
        return None

    lib = (chart.get("library") or "plotly").lower()
    ctype = (chart.get("type") or chart.get("chart_type") or "none").lower()
    x = chart.get("x")
    y = chart.get("y")
    title = chart.get("title")

    lat = chart.get("lat") or ("lat" if "lat" in df.columns else None)
    lon = chart.get("lon") or ("lon" if "lon" in df.columns else None)
    size = chart.get("size")
    color = chart.get("color")

    if ctype in ("none", "table"):
        return None

    if lib == "plotly":
        import plotly.express as px

        if ctype == "bar":
            if x and y and x in df.columns and y in df.columns:
                kwargs = {"x": x, "y": y, "title": title}
                if color and color in df.columns:
                    kwargs["color"] = color
                return px.bar(df, **kwargs)
            if len(df.columns) >= 2:
                return px.bar(df, x=df.columns[0], y=df.columns[1], title=title)

        if ctype == "line":
            if x and y and x in df.columns and y in df.columns:
                kwargs = {"x": x, "y": y, "title": title}
                if color and color in df.columns:
                    kwargs["color"] = color
                return px.line(df, **kwargs)
            if len(df.columns) >= 2:
                return px.line(df, x=df.columns[0], y=df.columns[1], title=title)

        if ctype == "scatter":
            if x and y and x in df.columns and y in df.columns:
                kwargs = {"x": x, "y": y, "title": title}
                if color and color in df.columns:
                    kwargs["color"] = color
                return px.scatter(df, **kwargs)
            if len(df.columns) >= 2:
                return px.scatter(df, x=df.columns[0], y=df.columns[1], title=title)

        if ctype == "hist":
            col = x if x in df.columns else (df.columns[0] if len(df.columns) >= 1 else None)
            if col:
                return px.histogram(df, x=col, title=title)

        if ctype == "box":
            col = y if y in df.columns else (df.columns[0] if len(df.columns) >= 1 else None)
            if col:
                return px.box(df, y=col, title=title)

        if ctype == "heatmap":
            if x and y and x in df.columns and y in df.columns:
                return px.density_heatmap(df, x=x, y=y, title=title)
            # correlation heatmap as fallback
            num = df.select_dtypes(include="number")
            if num.shape[1] >= 2:
                return px.imshow(num.corr(), title=title)

        if ctype == "pie":
            if x and y and x in df.columns and y in df.columns:
                return px.pie(df, names=x, values=y, title=title)

        if ctype == "map":
            if lat and lon and lat in df.columns and lon in df.columns:
                args = {"lat": lat, "lon": lon}
                if size and size in df.columns:
                    args["size"] = size
                if color and color in df.columns:
                    args["color"] = color
                fig = px.scatter_geo(df, **args, title=title)
                return fig

        return None

    if lib == "seaborn":
        import matplotlib.pyplot as plt
        import seaborn as sns

        fig = plt.figure()
        ax = fig.add_subplot(111)

        if ctype == "bar":
            if x and y and x in df.columns and y in df.columns:
                sns.barplot(data=df, x=x, y=y, ax=ax)
            elif len(df.columns) >= 2:
                sns.barplot(data=df, x=df.columns[0], y=df.columns[1], ax=ax)

        elif ctype == "line":
            if x and y and x in df.columns and y in df.columns:
                sns.lineplot(data=df, x=x, y=y, ax=ax)
            elif len(df.columns) >= 2:
                sns.lineplot(data=df, x=df.columns[0], y=df.columns[1], ax=ax)

        elif ctype == "scatter":
            if x and y and x in df.columns and y in df.columns:
                sns.scatterplot(data=df, x=x, y=y, ax=ax)
            elif len(df.columns) >= 2:
                sns.scatterplot(data=df, x=df.columns[0], y=df.columns[1], ax=ax)

        elif ctype == "hist":
            col = x if x in df.columns else (df.columns[0] if len(df.columns) >= 1 else None)
            if col:
                sns.histplot(data=df, x=col, ax=ax)

        elif ctype == "box":
            col = y if y in df.columns else (df.columns[0] if len(df.columns) >= 1 else None)
            if col:
                sns.boxplot(data=df, y=col, ax=ax)

        elif ctype == "heatmap":
            num = df.select_dtypes(include="number")
            if num.shape[1] >= 2:
                sns.heatmap(num.corr(), ax=ax)

        else:
            return None

        if title:
            ax.set_title(title)
        fig.tight_layout()
        return fig

    return None
