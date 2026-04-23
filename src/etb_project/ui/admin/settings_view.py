"""Admin: read-only environment overview (secrets masked)."""

from __future__ import annotations

import os
import re

import streamlit as st

_SECRET_KEY_RE = re.compile(
    r"(API_KEY|_TOKEN|_PASSWORD|SECRET|BEARER)$",
    re.IGNORECASE,
)


def _is_secret_key(key: str) -> bool:
    return bool(_SECRET_KEY_RE.search(key))


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


def _stat_pill(label: str, value: str, color: str = "#a78bfa") -> str:
    return (
        f'<span style="display:inline-flex;align-items:center;gap:0.4rem;'
        f'padding:0.32rem 0.78rem;border-radius:999px;'
        f'background:{color}1a;border:1px solid {color}55;'
        f'color:{color};font-size:0.78rem;font-weight:600;">'
        f'{label}: <span style="color:#ffffff;font-weight:700;">{value}</span></span>'
    )


def _render_kv_card(
    title: str,
    subtitle: str,
    items: list[tuple[str, str]],
    accent: str = "#a78bfa",
    mask_value: bool = False,
) -> None:
    if not items:
        return

    rows_html = []
    for k, v in items:
        value_style = (
            "color:#fecaca;font-family:'JetBrains Mono', ui-monospace, monospace;"
            if mask_value
            else "color:#e7e7ef;font-family:'JetBrains Mono', ui-monospace, monospace;"
        )
        rows_html.append(
            f'<div style="display:grid;grid-template-columns:minmax(200px,280px) 1fr;'
            f'gap:1rem;padding:0.7rem 1rem;border-bottom:1px solid rgba(236,236,244,0.05);'
            f'align-items:center;">'
            f'<div style="font-size:0.82rem;font-weight:600;'
            f'color:rgba(219,210,250,0.85);letter-spacing:0.01em;'
            f'word-break:break-all;">{k}</div>'
            f'<div style="font-size:0.85rem;{value_style}word-break:break-all;">{v}</div>'
            f'</div>'
        )

    st.markdown(
        f'<div style="margin:0.6rem 0 1.2rem 0;'
        f'border:1px solid rgba(236,236,244,0.10);border-radius:14px;'
        f'background:rgba(17,17,24,0.35);overflow:hidden;">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'gap:0.75rem;padding:0.9rem 1rem;'
        f'border-bottom:1px solid rgba(236,236,244,0.08);'
        f'background:linear-gradient(180deg,{accent}10,transparent);">'
        f'<div>'
        f'<div style="font-size:1rem;font-weight:600;color:#ffffff;">{title}</div>'
        f'<div style="font-size:0.78rem;color:rgba(219,210,250,0.55);'
        f'margin-top:0.12rem;">{subtitle}</div>'
        f'</div>'
        f'{_stat_pill("Entries", str(len(items)), accent)}'
        f'</div>'
        f'<div>{"".join(rows_html)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_admin_settings() -> None:
    _section_header(
        "Settings",
        "Read-only environment overview. Restart services after changing variables.",
    )

    top_cols = st.columns([2, 3], gap="medium", vertical_alignment="center")
    with top_cols[0]:
        reveal_len = st.checkbox(
            "Show secret lengths only (not values)",
            value=False,
            help="When enabled, secret values are replaced by their character count.",
        )
    with top_cols[1]:
        st.markdown(
            '<div style="padding:0.55rem 0.9rem;border-radius:10px;'
            'background:rgba(74,222,128,0.08);border:1px solid rgba(74,222,128,0.28);'
            'color:#bbf7d0;font-size:0.82rem;">'
            'Secrets are masked by default. Never share raw tokens or keys.'
            '</div>',
            unsafe_allow_html=True,
        )

    search = st.text_input(
        "Filter keys",
        placeholder="e.g. ORCHESTRATOR, API_KEY, USER…",
        label_visibility="collapsed",
    ).strip().upper()

    keys = sorted(os.environ.keys())
    urls: list[tuple[str, str]] = []
    other: list[tuple[str, str]] = []
    masked: list[tuple[str, str]] = []

    for k in keys:
        if k.startswith("_"):
            continue
        if search and search not in k.upper():
            continue
        v = os.environ.get(k, "")
        if "URL" in k or k.endswith("_HOST") or k.endswith("_DIR") or k.endswith("_PATH"):
            urls.append((k, v))
        elif _is_secret_key(k):
            if reveal_len and v:
                masked.append((k, f"set ({len(v)} chars)"))
            else:
                masked.append((k, "•••••••• (hidden)"))
        else:
            other.append((k, v))

    summary_html = (
        '<div style="display:flex;gap:0.6rem;flex-wrap:wrap;margin:0.4rem 0 0.9rem 0;">'
        f'{_stat_pill("URLs / paths", str(len(urls)), "#60a5fa")}'
        f'{_stat_pill("Other", str(len(other)), "#a78bfa")}'
        f'{_stat_pill("Secrets", str(len(masked)), "#f472b6")}'
        '</div>'
    )
    st.markdown(summary_html, unsafe_allow_html=True)

    _render_kv_card(
        "URLs & Paths",
        "Base URLs, hosts, and filesystem paths used by the services.",
        urls,
        accent="#60a5fa",
    )

    _render_kv_card(
        "Configuration",
        "Non-sensitive environment variables.",
        other[:120],
        accent="#a78bfa",
    )
    if len(other) > 120:
        st.caption(f"… and {len(other) - 120} more keys omitted for brevity.")

    _render_kv_card(
        "Security",
        "Credentials, API keys, and tokens. Values are masked.",
        masked,
        accent="#f472b6",
        mask_value=True,
    )
