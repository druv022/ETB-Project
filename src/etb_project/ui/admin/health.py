"""Admin: orchestrator + retriever health / ready."""

from __future__ import annotations

import time
from typing import Any

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


def _latency_color(ms: float | None) -> str:
    if ms is None:
        return "#a3a3b2"
    if ms < 100:
        return "#4ade80"
    if ms < 500:
        return "#facc15"
    return "#f87171"


def _status_pill(label: str, color: str, dot: str = "●") -> str:
    return (
        f'<span style="display:inline-flex;align-items:center;gap:0.4rem;'
        f'padding:0.28rem 0.72rem;border-radius:999px;'
        f'background:{color}22;border:1px solid {color}55;'
        f'color:{color};font-size:0.82rem;font-weight:600;'
        f'letter-spacing:0.02em;">{dot} {label}</span>'
    )


def _metric_box(label: str, value: str, value_color: str = "#e7e7ef") -> str:
    return (
        f'<div style="padding:0.75rem 1rem;border-radius:12px;'
        f'background:rgba(255,255,255,0.03);'
        f'border:1px solid rgba(236,236,244,0.10);">'
        f'<div style="font-size:0.72rem;text-transform:uppercase;'
        f'letter-spacing:0.08em;color:rgba(219,210,250,0.65);'
        f'margin-bottom:0.25rem;">{label}</div>'
        f'<div style="font-size:1.1rem;font-weight:600;color:{value_color};">{value}</div>'
        f'</div>'
    )


def _render_check(
    title: str,
    subtitle: str,
    ok: bool,
    warn: bool,
    err: str | None,
    latency_ms: float | None,
    payload: Any,
) -> None:
    if err:
        status = _status_pill("Unreachable", "#f87171", "✕")
    elif ok:
        status = _status_pill("Operational", "#4ade80", "●")
    elif warn:
        status = _status_pill("Not ready", "#facc15", "●")
    else:
        status = _status_pill("Unknown", "#a3a3b2", "●")

    header = (
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'gap:0.75rem;margin-bottom:0.85rem;">'
        f'<div>'
        f'<div style="font-size:1rem;font-weight:600;color:#f5f5fa;">{title}</div>'
        f'<div style="font-size:0.78rem;color:rgba(219,210,250,0.55);'
        f'margin-top:0.1rem;">{subtitle}</div>'
        f'</div>'
        f'{status}'
        f'</div>'
    )
    st.markdown(header, unsafe_allow_html=True)

    lat_label = f"{latency_ms:.0f} ms" if latency_ms is not None else "—"
    st.markdown(
        _metric_box("Latency", lat_label, _latency_color(latency_ms)),
        unsafe_allow_html=True,
    )

    if err:
        st.markdown(
            f'<div style="margin-top:0.6rem;padding:0.7rem 0.9rem;border-radius:10px;'
            f'background:rgba(248,113,113,0.08);border:1px solid rgba(248,113,113,0.35);'
            f'color:#fecaca;font-size:0.85rem;">{err}</div>',
            unsafe_allow_html=True,
        )
        return

    with st.expander("Response details", expanded=False):
        st.json(payload or {})


def _render_service_card(name: str, base: str) -> None:
    st.markdown(
        f'<div style="margin:0.4rem 0 0.6rem 0;'
        f'padding:0.2rem 0 0.4rem 0;">'
        f'<div style="font-size:1.35rem;font-weight:600;color:#ffffff;'
        f'letter-spacing:-0.01em;">{name}</div>'
        f'<div style="font-size:0.82rem;color:rgba(219,210,250,0.55);'
        f'margin-top:0.15rem;">{base}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    health_payload, health_err, health_ms = _fetch_public(f"{base}/v1/health")
    ready_payload, ready_err, ready_ms = _fetch_public(f"{base}/v1/ready")

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        _render_check(
            title="Health",
            subtitle="/v1/health",
            ok=health_err is None,
            warn=False,
            err=health_err,
            latency_ms=health_ms,
            payload=health_payload,
        )
    with c2:
        ready_flag = bool((ready_payload or {}).get("ready"))
        _render_check(
            title="Readiness",
            subtitle="/v1/ready",
            ok=ready_err is None and ready_flag,
            warn=ready_err is None and not ready_flag,
            err=ready_err,
            latency_ms=ready_ms,
            payload=ready_payload,
        )


def render_admin_health() -> None:
    st.markdown(
        '<div style="margin-bottom:1.25rem;">'
        '<div style="font-size:1.9rem;font-weight:600;color:#ffffff;'
        'letter-spacing:-0.02em;">System health</div>'
        '<div style="font-size:0.95rem;color:rgba(219,210,250,0.65);'
        'margin-top:0.25rem;">Live status of the orchestrator and retriever services.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    orch = orchestrator_base_url()
    ret = retriever_base_url()

    _render_service_card("Orchestrator", orch)
    st.markdown(
        '<div style="height:1px;background:rgba(236,236,244,0.08);'
        'margin:1.4rem 0;"></div>',
        unsafe_allow_html=True,
    )
    _render_service_card("Retriever", ret)
