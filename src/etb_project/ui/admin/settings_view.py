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


def render_admin_settings() -> None:
    st.subheader("Settings")
    st.caption("Read-only. Restart services after changing environment variables.")

    reveal_len = st.checkbox("Show secret lengths only (not values)", value=False)

    keys = sorted(os.environ.keys())
    urls: list[tuple[str, str]] = []
    other: list[tuple[str, str]] = []
    masked: list[tuple[str, str]] = []

    for k in keys:
        if k.startswith("_"):
            continue
        v = os.environ.get(k, "")
        if "URL" in k or k.endswith("_HOST") or k.endswith("_DIR"):
            urls.append((k, v))
        elif _is_secret_key(k):
            if reveal_len and v:
                masked.append((k, f"<set, {len(v)} chars>"))
            else:
                masked.append((k, "***"))
        else:
            other.append((k, v))

    st.markdown("#### URLs / paths")
    for k, v in urls:
        st.text(f"{k}={v}")

    st.markdown("#### Other")
    for k, v in other[:80]:
        st.text(f"{k}={v}")
    if len(other) > 80:
        st.caption(f"… and {len(other) - 80} more keys omitted.")

    st.markdown("#### Security (masked)")
    for k, v in masked:
        st.text(f"{k}={v}")
