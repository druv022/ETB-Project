"""Admin: recent HTTP audit logs from orchestrator and retriever."""

from __future__ import annotations

import json

import requests
import streamlit as st

from etb_project.ui.admin.http_helpers import admin_bearer_headers, format_request_error
from etb_project.ui.auth_credentials import (
    admin_api_token,
    orchestrator_base_url,
    retriever_base_url,
)


def _fetch_logs(base: str, limit: int) -> tuple[str, str | None, int]:
    tok = admin_api_token()
    if not tok:
        return (
            "",
            "Set ``ETB_ADMIN_API_TOKEN`` in the environment or ``.streamlit/secrets.toml``.",
            0,
        )
    url = f"{base}/v1/admin/recent-logs"
    try:
        r = requests.get(
            url,
            params={"limit": limit},
            headers=admin_bearer_headers(),
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        lines = data.get("lines") or []
        return json.dumps(lines, indent=2), None, len(lines)
    except requests.RequestException as exc:
        return "", format_request_error(exc), 0


def _section_header(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div style="margin-bottom:1.1rem;">'
        f'<div style="font-size:1.9rem;font-weight:600;color:#ffffff;'
        f'letter-spacing:-0.02em;">{title}</div>'
        f'<div style="font-size:0.95rem;color:rgba(219,210,250,0.65);'
        f'margin-top:0.25rem;">{subtitle}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _info_banner(kind: str, message: str) -> None:
    colors = {
        "warn": ("#facc15", "rgba(250,204,21,0.08)", "rgba(250,204,21,0.35)"),
        "info": ("#a3a3b2", "rgba(236,236,244,0.04)", "rgba(236,236,244,0.12)"),
        "error": ("#f87171", "rgba(248,113,113,0.08)", "rgba(248,113,113,0.35)"),
    }
    fg, bg, border = colors.get(kind, colors["info"])
    st.markdown(
        f'<div style="padding:0.85rem 1rem;border-radius:12px;'
        f'background:{bg};border:1px solid {border};'
        f'color:{fg};font-size:0.88rem;line-height:1.45;">'
        f'{message}</div>',
        unsafe_allow_html=True,
    )


def _meta_row(line_count: int, limit: int, source: str) -> None:
    st.markdown(
        f'<div style="display:flex;gap:0.6rem;flex-wrap:wrap;'
        f'margin:0.4rem 0 0.9rem 0;">'
        f'<span style="padding:0.32rem 0.75rem;border-radius:999px;'
        f'background:rgba(74,222,128,0.10);border:1px solid rgba(74,222,128,0.35);'
        f'color:#4ade80;font-size:0.78rem;font-weight:600;">'
        f'● {line_count} lines</span>'
        f'<span style="padding:0.32rem 0.75rem;border-radius:999px;'
        f'background:rgba(236,236,244,0.05);border:1px solid rgba(236,236,244,0.14);'
        f'color:rgba(236,236,244,0.85);font-size:0.78rem;font-weight:500;">'
        f'Limit: {limit}</span>'
        f'<span style="padding:0.32rem 0.75rem;border-radius:999px;'
        f'background:rgba(236,236,244,0.05);border:1px solid rgba(236,236,244,0.14);'
        f'color:rgba(236,236,244,0.85);font-size:0.78rem;font-weight:500;">'
        f'{source}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_log_panel(base: str, limit: int, source: str) -> None:
    text, err, count = _fetch_logs(base, limit)
    if err:
        _info_banner("warn", err)
        return
    if not text:
        _info_banner("info", "No log lines returned.")
        return
    _meta_row(count, limit, source)
    st.code(text, language="json")


def render_admin_logs() -> None:
    _section_header(
        "Logs",
        "Recent HTTP audit entries from the orchestrator and retriever services.",
    )

    top_cols = st.columns([3, 1], gap="medium", vertical_alignment="bottom")
    with top_cols[0]:
        limit = st.slider(
            "Line limit",
            min_value=10,
            max_value=500,
            value=100,
            step=10,
            help="How many of the most recent audit lines to retrieve.",
        )
    with top_cols[1]:
        if st.button("Refresh logs", use_container_width=True):
            st.session_state["_logs_refresh"] = True

    tab_o, tab_r = st.tabs(["Orchestrator", "Retriever"])
    with tab_o:
        _render_log_panel(orchestrator_base_url(), limit, orchestrator_base_url())
    with tab_r:
        _render_log_panel(retriever_base_url(), limit, retriever_base_url())
