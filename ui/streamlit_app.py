"""ui.streamlit_app

Streamlit UI (company_name-themed):
- Role selector (CEO/CFO/CTO) with built-in question shortcuts
- Chat interface
- Debug mode inline panels (disabled when debug off)
- Controls: max rows/cols/timeout/backend
- Renders executive markdown + charts/tables returned by orchestrator
"""

from __future__ import annotations

import time
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import streamlit as st

from app.env_loader import load_env
from app.config import Settings
from app.contracts.models import ChatRequest, UISettings
from app.main import handle_chat
from ui.ui_theme import css

from app.available_data.registry import load_built_in_questions, load_intent_registry


@st.cache_data(show_spinner=False)
def _load_questions():
    qs = load_built_in_questions()
    reg = load_intent_registry()
    return qs, reg


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
        st.session_state.masked = (os.environ.get("DATA_MASKED", "true").strip().lower() in ("1", "true", "yes", "y", "on"))
    if "role" not in st.session_state:
        st.session_state.role = "CEO"
    if "pending_confirmation" not in st.session_state:
        st.session_state.pending_confirmation = None  # {prompt, intent}


def _render_debug(resp):
    panels = []
    if resp.traces:
        for t in resp.traces:
            panels.append({"title": t.step_name, "body": json.dumps(t.payload, indent=2, default=str)})
    return panels


def main():
    load_env()
    settings = Settings.load()
    _init_state(settings)

    st.set_page_config(page_title="Analytics AI", page_icon="📊", layout="wide")
    st.markdown(css(), unsafe_allow_html=True)

    st.markdown(
        "<div class='company-header'><span class='company-badge'>📊 Analytics AI</span>"
        "<b>Analytics AI</b>"
        "<span class='company-muted'>Executive reporting and trends</span></div>",
        unsafe_allow_html=True,
    )

    qs, reg = _load_questions()

    with st.sidebar:
        st.markdown("### Role")
        c1, c2, c3 = st.columns(3)
        if c1.button("CEO", width="stretch"):
            st.session_state.role = "CEO"
        if c2.button("CFO", width="stretch"):
            st.session_state.role = "CFO"
        if c3.button("CTO", width="stretch"):
            st.session_state.role = "CTO"

        st.markdown(f"Selected role: **{st.session_state.role}**")
        st.divider()

        st.markdown("### Settings")
        st.session_state.debug = st.toggle("Debug mode", value=st.session_state.debug)
        st.session_state.max_rows = st.number_input("Max rows (UI)", min_value=1, max_value=500, value=int(st.session_state.max_rows))
        st.session_state.max_cols = st.number_input("Max columns (UI)", min_value=1, max_value=200, value=int(st.session_state.max_cols))
        st.session_state.timeout = st.number_input("Max execution time (sec)", min_value=1, max_value=120, value=int(st.session_state.timeout))
        st.session_state.backend = st.selectbox("DB backend (fallback path)", options=["sqlserver", "sqlite"], index=0 if st.session_state.backend == "sqlserver" else 1)
        st.session_state.masked = st.toggle("Data is masked or hashed", value=st.session_state.masked)
        st.caption("Use Debug mode to show step-by-step traces.")

    # Render chat history
    for m in st.session_state.messages:
        with st.chat_message(m.get("role", "assistant")):
            st.markdown(m.get("content", ""))

            # visuals
            if m.get("charts"):
                for fig in m["charts"]:
                    if fig is None:
                        continue
                    if hasattr(fig, "to_dict"):
                        st.plotly_chart(fig, width="stretch")
                    else:
                        st.pyplot(fig, clear_figure=False)

            if m.get("tables"):
                for df in m["tables"]:
                    if df is not None:
                        st.dataframe(df, width="stretch")

            if st.session_state.debug and m.get("debug_panels"):
                for panel in m["debug_panels"]:
                    with st.expander(panel["title"], expanded=False):
                        st.code(panel["body"], language="json")

            # Confirmation buttons
            if m.get("needs_confirmation") and st.session_state.pending_confirmation:
                cc1, cc2 = st.columns(2)
                if cc1.button("Search elsewhere", width="stretch", key=f"confirm_yes_{m['id']}"):
                    info = st.session_state.pending_confirmation
                    st.session_state.pending_confirmation = None
                    _send_and_render(info["prompt"], selected_intent=info.get("intent"), confirm_search_elsewhere=True)
                    st.rerun()
                if cc2.button("No, I'll rephrase", width="stretch", key=f"confirm_no_{m['id']}"):
                    st.session_state.pending_confirmation = None
                    st.rerun()

    # Suggested questions attached to chat area
    st.markdown("### Suggested questions")
    role = st.session_state.role
    role_qs = [q for q in qs if role in [r.upper() for r in q.roles]]
    cols = st.columns(4)
    for i, q in enumerate(role_qs[:20]):
        if cols[i % 4].button(q.text, width="stretch"):
            st.session_state.pending_confirmation = None
            st.session_state.messages.append({"role": "user", "content": q.text})
            _send_and_render(q.text, selected_intent=q.intent)
            st.rerun()

    prompt = st.chat_input("Ask a question...")
    if prompt:
        st.session_state.pending_confirmation = None
        st.session_state.messages.append({"role": "user", "content": prompt})
        _send_and_render(prompt, selected_intent=None)
        st.rerun()


def _send_and_render(prompt: str, selected_intent: str | None, confirm_search_elsewhere: bool = False):
    ui_settings = UISettings(
        debug=bool(st.session_state.debug),
        max_rows_ui=int(st.session_state.max_rows),
        max_cols_ui=int(st.session_state.max_cols),
        max_exec_seconds=int(st.session_state.timeout),
        backend=st.session_state.backend,
    )

    history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-12:]]
    meta = {
        "role": st.session_state.role,
        "selected_intent": selected_intent,
        "confirm_search_elsewhere": confirm_search_elsewhere,
    }
    req = ChatRequest(session_id="streamlit", message=prompt, ui=ui_settings, history=history, meta=meta)

    phases = [
        "Understanding your request",
        "Routing to the right data path",
        "Generating analysis",
        "Preparing final response",
    ]

    with st.status("Working on your request...", expanded=True) as status:
        start = time.time()
        status.write("Started")
        try:
            with ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(handle_chat, req)
                phase_idx = 0
                last_tick = 0.0
                while not future.done():
                    now = time.time()
                    if now - last_tick >= 0.8:
                        elapsed = now - start
                        phase = phases[min(phase_idx, len(phases) - 1)]
                        status.update(label=f"{phase} • {elapsed:.1f}s", state="running")
                        if phase_idx < len(phases) - 1:
                            phase_idx += 1
                        last_tick = now
                    time.sleep(0.1)
                resp = future.result()
            elapsed = time.time() - start
            status.update(label=f"Done • {elapsed:.1f}s", state="complete", expanded=False)
        except Exception:
            status.update(label="Request failed", state="error", expanded=True)
            raise

    charts = []
    tables = []
    # report blocks
    if getattr(resp, "report_blocks", None):
        import pandas as pd
        for b in resp.report_blocks:
            cols = b.get("columns") or []
            rows = b.get("rows") or []
            if cols and rows:
                df = pd.DataFrame(rows, columns=cols)
                tables.append(df)
            fig = b.get("fig")
            if fig is not None:
                charts.append(fig)

    debug_panels = _render_debug(resp) if st.session_state.debug else []

    msg = {
        "role": "assistant",
        "content": resp.answer,
        "charts": charts,
        "tables": tables,
        "debug_panels": debug_panels,
    }

    if resp.status == "need_confirmation":
        # Store pending confirmation context
        st.session_state.pending_confirmation = {"prompt": prompt, "intent": selected_intent}
        msg["needs_confirmation"] = True
        msg["id"] = f"m{len(st.session_state.messages)}"
    st.session_state.messages.append(msg)


if __name__ == "__main__":
    main()
