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


def _fetch_logs(base: str, limit: int) -> tuple[str, str | None]:
    tok = admin_api_token()
    if not tok:
        return (
            "",
            "Set ``ETB_ADMIN_API_TOKEN`` in the environment or ``.streamlit/secrets.toml``.",
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
        return json.dumps(lines, indent=2), None
    except requests.RequestException as exc:
        return "", format_request_error(exc)


def render_admin_logs() -> None:
    st.subheader("Logs")
    limit = st.slider("Line limit", min_value=10, max_value=500, value=100, step=10)
    if st.button("Refresh logs"):
        st.session_state["_logs_refresh"] = True

    tab_o, tab_r = st.tabs(["Orchestrator", "Retriever"])
    with tab_o:
        text, err = _fetch_logs(orchestrator_base_url(), limit)
        if err:
            st.warning(err)
        elif text:
            st.code(text, language="json")
        else:
            st.caption("No log lines returned.")
    with tab_r:
        text2, err2 = _fetch_logs(retriever_base_url(), limit)
        if err2:
            st.warning(err2)
        elif text2:
            st.code(text2, language="json")
        else:
            st.caption("No log lines returned.")
