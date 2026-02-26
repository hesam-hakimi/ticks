"""ui.streamlit_app

Streamlit UI (company_name-themed):
- Chat interface
- Debug mode inline panels (disabled when debug off)
- Controls: max rows/cols/timeout/backend
- Supports analytics reports with rich markdown + Plotly/Seaborn charts.
"""

from __future__ import annotations
import json
import os
import streamlit as st

from app.config import Settings
from app.contracts.models import ChatRequest, UISettings
from app.main import handle_chat
from ui.ui_theme import css

from app.viz.chart_renderer import render_chart


def _init_state(settings: Settings):
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "debug" not in st.session_state:
        st.session_state.debug = settings.default_debug
    if "max_rows" not in st.session_state:
        st.session_state.max_rows = settings.default_max_rows
    if "max_cols" not in st.session_state:
        st.session_state.max_cols = settings.default_max_cols
    if "timeout" not in st.session_state:
        st.session_state.timeout = settings.default_timeout_seconds
    if "backend" not in st.session_state:
        st.session_state.backend = settings.db_backend
    if "masked" not in st.session_state:
        st.session_state.masked = (os.environ.get("DATA_MASKED", "true").strip().lower() in ("1","true","yes","y","on"))


def main():
    settings = Settings.load()
    _init_state(settings)

    st.set_page_config(page_title="company_name Text-to-SQL", page_icon="✅", layout="wide")
    st.markdown(css(), unsafe_allow_html=True)

    st.markdown(
        "<div class='company-header'><span class='company-badge'>company_name</span>"
        "<b>Analytics Chat</b>"
        "<span class='company-muted'>Text-to-SQL + Report (Phase 1+2)</span></div>",
        unsafe_allow_html=True,
    )

    if st.session_state.masked:
        st.info("This environment contains **masked/hashed values**. PII/PCI columns are protected.", icon="🔒")

    with st.sidebar:
        st.markdown("### Settings")
        st.session_state.debug = st.toggle("Debug mode", value=st.session_state.debug)
        st.session_state.max_rows = st.number_input("Max rows (UI)", min_value=1, max_value=500, value=int(st.session_state.max_rows))
        st.session_state.max_cols = st.number_input("Max columns (UI)", min_value=1, max_value=200, value=int(st.session_state.max_cols))
        st.session_state.timeout = st.number_input("Max execution time (sec)", min_value=1, max_value=120, value=int(st.session_state.timeout))
        st.session_state.backend = st.selectbox("DB backend", options=["sqlserver", "sqlite"], index=0 if st.session_state.backend == "sqlserver" else 1)
        st.session_state.masked = st.toggle("Data is masked/hashed", value=st.session_state.masked)
        st.divider()
        st.caption("Debug mode shows step-by-step traces. Turn it off for business users.")

    # render history
    for m in st.session_state.messages:
        role = m.get("role", "assistant")
        with st.chat_message(role):
            st.markdown(m.get("content", ""))

            if m.get("charts"):
                for ch in m["charts"]:
                    if ch is None:
                        continue
                    # Plotly figures have to be rendered with st.plotly_chart
                    if hasattr(ch, "to_dict"):
                        st.plotly_chart(ch, use_container_width=True)
                    else:
                        st.pyplot(ch, clear_figure=False)

            if m.get("tables"):
                for df in m["tables"]:
                    if df is not None:
                        st.dataframe(df, use_container_width=True)

            if st.session_state.debug and m.get("debug_panels"):
                for panel in m["debug_panels"]:
                    with st.expander(panel["title"], expanded=False):
                        st.code(panel["body"], language="json")

    prompt = st.chat_input("Ask a data question or request an analytics report...")
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    ui_settings = UISettings(
        debug=bool(st.session_state.debug),
        max_rows_ui=int(st.session_state.max_rows),
        max_cols_ui=int(st.session_state.max_cols),
        max_exec_seconds=int(st.session_state.timeout),
        backend=st.session_state.backend,
    )

    history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-12:]]
    req = ChatRequest(session_id="streamlit", message=prompt, ui=ui_settings, history=history)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            resp = handle_chat(req)

        debug_panels = []
        if ui_settings.debug and resp.traces:
            for t in resp.traces:
                debug_panels.append({"title": t.step_name, "body": json.dumps(t.payload, indent=2, default=str)})

        # Response: markdown is important for reports
        st.markdown(resp.answer)

        charts = []
        tables = []

        # If the response includes a single query result (DATA_QA), show table preview
        if resp.result and resp.result.columns:
            import pandas as pd
            df = pd.DataFrame(resp.result.rows, columns=resp.result.columns)
            tables.append(df)
            st.dataframe(df, use_container_width=True)

        # If debug is enabled, try to render charts/tables from report traces (report planner/writer)
        if ui_settings.debug:
            # Look for report_planner trace which includes query chart specs
            try:
                planner = None
                for t in resp.traces or []:
                    if t.step_name == "report_planner":
                        planner = t.payload
                if planner and isinstance(planner, dict) and planner.get("queries"):
                    # We don't have raw executed data in response; charts will render when extended report payload is added.
                    pass
            except Exception:
                pass

        st.session_state.messages.append({
            "role": "assistant",
            "content": resp.answer,
            "debug_panels": debug_panels,
            "charts": charts,
            "tables": tables,
        })


if __name__ == "__main__":
    main()
