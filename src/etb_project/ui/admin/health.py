"""Admin: orchestrator + retriever health / ready."""

from __future__ import annotations

import time

import requests
import streamlit as st

from etb_project.ui.auth_credentials import orchestrator_base_url, retriever_base_url


def _fetch_public(url: str) -> tuple[dict | None, str | None, float | None]:
    t0 = time.perf_counter()
    try:
        r = requests.get(url, timeout=15)
        ms = (time.perf_counter() - t0) * 1000
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}", ms
        return r.json(), None, ms
    except requests.RequestException as exc:
        ms = (time.perf_counter() - t0) * 1000
        return None, str(exc), ms


def render_admin_health() -> None:
    st.subheader("System health")
    orch = orchestrator_base_url()
    ret = retriever_base_url()

    for name, base in (("Orchestrator", orch), ("Retriever", ret)):
        st.markdown(f"### {name}")
        c1, c2 = st.columns(2)
        with c1:
            h, err, lat = _fetch_public(f"{base}/v1/health")
            if err:
                st.error(f"Health: Unreachable — {err}")
            else:
                st.success(f"Health: OK ({lat:.0f} ms)" if lat else "Health: OK")
                st.json(h or {})
        with c2:
            rdy, err2, lat2 = _fetch_public(f"{base}/v1/ready")
            if err2:
                st.warning(f"Ready check: Unreachable — {err2}")
            else:
                data = rdy or {}
                ready_flag = data.get("ready")
                label = "Ready" if ready_flag else "Not ready"
                st.info(f"{label} ({lat2:.0f} ms)" if lat2 else label)
                st.json(data)
