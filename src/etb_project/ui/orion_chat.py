"""Orion chat UI: orchestrator client, sources, and asset loading."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
import streamlit as st

from etb_project.ui.asset_paths import (
    asset_request_headers,
    derive_asset_path_from_stored_path,
    display_name_for_source_file,
)
from etb_project.ui.auth_credentials import orchestrator_api_key, orchestrator_base_url


def call_orchestrator_chat(session_id: str, message: str) -> tuple[str, list[dict]]:
    """POST /v1/chat; sends Bearer when ``ETB_ORCHESTRATOR_API_KEY`` is set."""
    base_url = orchestrator_base_url()
    url = f"{base_url}/v1/chat"
    payload = {
        "session_id": session_id,
        "message": message,
        "return_sources": True,
    }
    headers: dict[str, str] = {}
    key = orchestrator_api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=120)
    except requests.RequestException as exc:
        return (
            "Orion could not reach the Orchestrator service. "
            f"Please verify it is running and reachable at {base_url}. ({exc})",
            [],
        )
    if response.status_code == 401:
        return (
            "Orchestrator rejected the request (401). If ``ETB_ORCHESTRATOR_API_KEY`` is set "
            "on the server, set the same value in the UI environment or ``.streamlit/secrets.toml``.",
            [],
        )
    if response.status_code >= 500:
        hint = (
            "This is usually a failure **inside** the orchestrator (missing LLM API key, retriever error, or graph exception). "
            "Check `docker compose logs etb_orchestrator --tail 80` and ensure `.env` sets "
            "`OPENROUTER_API_KEY` or `OPENAI_API_KEY` (or set `ETB_LLM_PROVIDER=ollama` with Ollama running)."
        )
        return (
            f"The orchestrator returned **{response.status_code}** from `/v1/chat`. {hint}\n\n"
            f"Detail: `{response.text[:400]}`",
            [],
        )
    if response.status_code >= 400:
        return (
            f"The orchestrator rejected the request (**{response.status_code}**). "
            f"`{response.text[:500]}`",
            [],
        )
    data = response.json() if response.content else {}
    answer = str(data.get("answer") or "").strip()
    sources = data.get("sources") or []
    if not answer:
        answer = "Orion did not receive a valid answer from the Orchestrator."
    return answer, sources


def _asset_auth_configured() -> bool:
    return bool(
        (
            os.getenv("RETRIEVER_API_KEY")
            or os.getenv("ORCHESTRATOR_ASSET_BEARER_TOKEN")
            or ""
        ).strip()
    )


@st.cache_data(show_spinner=False, ttl=3600)
def _fetch_asset_bytes_cached(
    asset_path: str, _auth_configured: bool
) -> tuple[bytes, str] | None:
    if not asset_path.strip():
        return None
    base = orchestrator_base_url()
    url = f"{base}/v1/assets/{asset_path.lstrip('/')}"
    headers = asset_request_headers() if _auth_configured else {}
    try:
        resp = requests.get(url, timeout=30, headers=headers)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    ctype = resp.headers.get("content-type") or "application/octet-stream"
    return resp.content, ctype


def _fetch_asset_bytes(asset_path: str) -> tuple[bytes, str] | None:
    return _fetch_asset_bytes_cached(asset_path, _asset_auth_configured())


def _candidate_asset_paths_from_record(rec: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for key in ("asset_path",):
        v = rec.get(key)
        if isinstance(v, str) and v.strip():
            s = v.strip().lstrip("/")
            if s not in seen:
                seen.add(s)
                out.append(s)
    p = rec.get("path")
    if isinstance(p, str) and p.strip():
        derived = derive_asset_path_from_stored_path(p)
        if derived and derived not in seen:
            seen.add(derived)
            out.append(derived)
    return out


def _candidate_asset_paths_from_metadata(meta: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    ap = meta.get("asset_path")
    if isinstance(ap, str) and ap.strip():
        s = ap.strip().lstrip("/")
        if s not in seen:
            seen.add(s)
            out.append(s)
    p = meta.get("path")
    if isinstance(p, str) and p.strip():
        derived = derive_asset_path_from_stored_path(p)
        if derived and derived not in seen:
            seen.add(derived)
            out.append(derived)
    return out


def _fetch_first_working_asset(candidates: list[str]) -> tuple[bytes, str] | None:
    for c in candidates:
        got = _fetch_asset_bytes(c)
        if got is not None:
            return got
    return None


def _safe_path(value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return Path(value)
    except Exception:
        return None


def _format_source_header(i: int, meta: dict[str, Any]) -> str:
    source = meta.get("source")
    page = meta.get("page")
    total_pages = meta.get("total_pages")

    filename = "unknown"
    if isinstance(source, str) and source.strip():
        filename = display_name_for_source_file(source.strip()) or "unknown"

    parts: list[str] = [f"**{i}. {filename}**"]
    if isinstance(page, int):
        if isinstance(total_pages, int):
            parts.append(f"p.{page}/{total_pages}")
        else:
            parts.append(f"p.{page}")
    return " • ".join(parts)


def _extract_image_caption_records(meta: dict[str, Any]) -> list[dict[str, str]]:
    records = meta.get("image_captions")
    if not isinstance(records, list):
        return []
    out: list[dict[str, str]] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        path = rec.get("path")
        asset_path = rec.get("asset_path")
        caption = rec.get("caption")
        if not isinstance(caption, str) or not caption.strip():
            continue
        merged: dict[str, str] = {"caption": caption}
        if isinstance(path, str) and path.strip():
            merged["path"] = path
        if isinstance(asset_path, str) and asset_path.strip():
            merged["asset_path"] = asset_path
        elif isinstance(path, str) and path.strip():
            derived = derive_asset_path_from_stored_path(path)
            if derived:
                merged["asset_path"] = derived
        out.append(merged)
    return out


def _render_images_tab(content: str, meta: dict[str, Any]) -> None:
    image_caps = _extract_image_caption_records(meta)
    if image_caps:
        cols = st.columns(3)
        for idx, rec in enumerate(image_caps):
            with cols[idx % 3]:
                candidates = _candidate_asset_paths_from_record(rec)
                fetched = _fetch_first_working_asset(candidates)
                if fetched is not None:
                    data, _ctype = fetched
                    st.image(data, use_container_width=True)
                else:
                    img_path = _safe_path(rec.get("path"))
                    if img_path is not None and img_path.exists():
                        st.image(str(img_path), use_container_width=True)
                    else:
                        st.caption(
                            "Could not load image from the API. "
                            "If you deployed with `RETRIEVER_API_KEY`, set the same "
                            "value in the UI env as `RETRIEVER_API_KEY` (or "
                            "`ORCHESTRATOR_ASSET_BEARER_TOKEN`)."
                        )
                        if rec.get("path"):
                            st.caption(str(rec.get("path")))
                caption = rec.get("caption") or ""
                short = caption[:260] + ("…" if len(caption) > 260 else "")
                st.caption(short)
        return

    candidates = _candidate_asset_paths_from_metadata(meta)
    fetched = _fetch_first_working_asset(candidates)
    if fetched is not None:
        data, _ctype = fetched
        st.image(data, use_container_width=True)
        if content:
            st.caption(content[:4000])
        details: list[str] = []
        if meta.get("caption_source"):
            details.append(f"caption_source: {meta.get('caption_source')}")
        if meta.get("xref"):
            details.append(f"xref: {meta.get('xref')}")
        if meta.get("image_index"):
            details.append(f"image_index: {meta.get('image_index')}")
        if details:
            st.caption(" • ".join(details))
        return

    if candidates:
        st.caption("Failed to load image via /v1/assets/.")

    single_path = _safe_path(meta.get("path"))
    if single_path is not None:
        if single_path.exists():
            st.image(str(single_path), use_container_width=True)
        else:
            st.caption(str(single_path))

    if content:
        st.caption(content[:4000])

    path_meta_details: list[str] = []
    if meta.get("caption_source"):
        path_meta_details.append(f"caption_source: {meta.get('caption_source')}")
    if meta.get("xref"):
        path_meta_details.append(f"xref: {meta.get('xref')}")
    if meta.get("image_index"):
        path_meta_details.append(f"image_index: {meta.get('image_index')}")
    if path_meta_details:
        st.caption(" • ".join(path_meta_details))

    if not candidates and single_path is None:
        st.caption("No images for this source.")


def render_source_card(i: int, source: dict[str, Any]) -> None:
    content = (source.get("content") or "").strip()
    meta = source.get("metadata") or {}
    if not isinstance(meta, dict):
        meta = {}

    st.markdown(_format_source_header(i, meta))
    tab_key = f"source_tab::{i}::{meta.get('source')}::{meta.get('page')}::{meta.get('start_index')}"
    selected = st.radio(
        "Source view",
        ["Excerpt", "Images", "Raw"],
        horizontal=True,
        label_visibility="collapsed",
        key=tab_key,
    )
    if selected == "Excerpt":
        if content:
            st.markdown(content)
        else:
            st.caption("No excerpt content for this source.")
    elif selected == "Images":
        _render_images_tab(content, meta)
    else:
        st.json(meta, expanded=False)


# Inline SVG avatars as data URLs: small, crisp, and theme-consistent.
_ORION_ASSISTANT_AVATAR = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 40 40'>"
    "<defs>"
    "<radialGradient id='orb' cx='32%25' cy='28%25' r='75%25'>"
    "<stop offset='0%25' stop-color='%23f5ebff'/>"
    "<stop offset='30%25' stop-color='%23b49cff'/>"
    "<stop offset='65%25' stop-color='%236d28d9'/>"
    "<stop offset='100%25' stop-color='%231e1446'/>"
    "</radialGradient>"
    "<radialGradient id='glow' cx='50%25' cy='50%25' r='55%25'>"
    "<stop offset='0%25' stop-color='%23a78bfa' stop-opacity='0.55'/>"
    "<stop offset='100%25' stop-color='%23a78bfa' stop-opacity='0'/>"
    "</radialGradient>"
    "</defs>"
    "<circle cx='20' cy='20' r='19' fill='url(%23glow)'/>"
    "<circle cx='20' cy='20' r='15' fill='url(%23orb)'/>"
    "<ellipse cx='14.5' cy='13.5' rx='3.2' ry='2.2' fill='white' opacity='0.75'/>"
    "</svg>"
)

_ORION_USER_AVATAR = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 40 40'>"
    "<defs>"
    "<linearGradient id='ubg' x1='0%25' y1='0%25' x2='100%25' y2='100%25'>"
    "<stop offset='0%25' stop-color='%23ffffff' stop-opacity='0.22'/>"
    "<stop offset='100%25' stop-color='%23ffffff' stop-opacity='0.06'/>"
    "</linearGradient>"
    "</defs>"
    "<circle cx='20' cy='20' r='18.5' fill='url(%23ubg)' "
    "stroke='rgba(255,255,255,0.32)' stroke-width='1'/>"
    "<circle cx='20' cy='16' r='5.2' fill='rgba(255,255,255,0.88)'/>"
    "<path d='M9.5 32.5 C 11 25 15 23.5 20 23.5 C 25 23.5 29 25 30.5 32.5 Z' "
    "fill='rgba(255,255,255,0.88)'/>"
    "</svg>"
)


_ORION_HERO_HTML = """
<style>
  @keyframes orion-orb-float {
    0%, 100% { transform: translateY(0) scale(1); }
    50% { transform: translateY(-6px) scale(1.03); }
  }
  @keyframes orion-orb-spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
  .orion-hero {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.55rem;
    margin: 0.6rem auto 0.4rem auto;
    text-align: center;
    max-width: 720px;
  }
  .orion-orb-wrap {
    position: relative;
    width: 84px;
    height: 84px;
    display: flex;
    align-items: center;
    justify-content: center;
    animation: orion-orb-float 6s ease-in-out infinite;
    margin-bottom: 0.25rem;
  }
  .orion-orb {
    position: absolute;
    inset: 10px;
    border-radius: 50%;
    background:
      radial-gradient(circle at 30% 28%, #e3d5ff 0%, #a78bfa 28%, #6d28d9 62%, #1e1b4b 100%);
    box-shadow:
      inset -10px -14px 24px rgba(0,0,0,0.55),
      inset 8px 10px 20px rgba(255,255,255,0.18),
      0 14px 40px rgba(139, 92, 246, 0.45),
      0 0 60px rgba(139, 92, 246, 0.30);
  }
  .orion-orb-ring {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    border: 1px solid rgba(167, 139, 250, 0.45);
    filter: blur(0.4px);
    animation: orion-orb-spin 18s linear infinite;
  }
  .orion-orb-ring::before {
    content: "";
    position: absolute;
    top: -3px; left: 50%;
    width: 5px; height: 5px;
    background: #e9d5ff;
    border-radius: 50%;
    box-shadow: 0 0 10px #c4b5fd;
    transform: translateX(-50%);
  }
  .orion-orb-glow {
    position: absolute;
    inset: -14px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(167,139,250,0.40) 0%, rgba(167,139,250,0) 65%);
    filter: blur(6px);
    z-index: -1;
  }
  .orion-hero-title {
    font-size: clamp(2rem, 4vw, 2.6rem);
    font-weight: 600;
    letter-spacing: -0.02em;
    color: #ffffff;
    margin: 0;
    line-height: 1.1;
    background: linear-gradient(180deg, #ffffff 0%, #d8d4ff 100%);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .orion-hero-subtitle {
    font-size: 0.92rem;
    color: rgba(219, 210, 250, 0.70);
    max-width: 560px;
    margin: 0 auto;
    line-height: 1.45;
  }
  .orion-hero-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.22rem 0.65rem;
    border-radius: 999px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(236,236,244,0.12);
    color: rgba(236,236,244,0.78);
    font-size: 0.72rem;
    font-weight: 500;
    letter-spacing: 0.04em;
  }
  .orion-hero-badge .dot {
    width: 5px; height: 5px;
    border-radius: 50%;
    background: #4ade80;
    box-shadow: 0 0 8px #4ade80;
  }
</style>
<div class="orion-hero">
  <div class="orion-orb-wrap">
    <div class="orion-orb-glow"></div>
    <div class="orion-orb"></div>
    <div class="orion-orb-ring"></div>
  </div>
  <h1 class="orion-hero-title">Orion AI</h1>
  <span class="orion-hero-badge"><span class="dot"></span>Online · Executive Assistant</span>
  <p class="orion-hero-subtitle">__SUBTITLE__</p>
  __SIGNED_IN__
</div>
"""


def render_orion() -> None:
    """Main Orion chat block (expects ``ensure_session_state`` already run)."""
    subtitle = (
        "Executive-focused assistant that refines your data requests so they "
        "are ready for retrieval from IndMex's internal systems."
    )

    username = st.session_state.get("auth_username") if st.session_state.get("auth_role") else None
    signed_in = (
        f'<div style="font-size:0.82rem;color:rgba(219,210,250,0.55);'
        f'margin-top:0.15rem;">Signed in as '
        f'<span style="color:#ffffff;font-weight:600;">{username}</span></div>'
        if username
        else ""
    )

    hero = _ORION_HERO_HTML.replace("__SUBTITLE__", subtitle).replace(
        "__SIGNED_IN__", signed_in
    )
    st.markdown(hero, unsafe_allow_html=True)

    for msg in st.session_state.messages:
        avatar = (
            _ORION_USER_AVATAR if msg["role"] == "user" else _ORION_ASSISTANT_AVATAR
        )
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    user_input = st.chat_input(
        "Describe the information you need from IndMex's data..."
    )

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user", avatar=_ORION_USER_AVATAR):
            st.markdown(user_input)

        with st.chat_message("assistant", avatar=_ORION_ASSISTANT_AVATAR):
            with st.spinner("Orion is retrieving an answer..."):
                reply, sources = call_orchestrator_chat(
                    st.session_state.session_id,
                    user_input,
                )
                st.markdown(reply)
                st.session_state.messages.append(
                    {"role": "assistant", "content": reply}
                )
                st.session_state.last_sources = sources or []

    if st.session_state.last_sources:
        with st.expander("Sources", expanded=True):
            for i, s in enumerate(st.session_state.last_sources, 1):
                if isinstance(s, dict):
                    render_source_card(i, s)
                else:
                    st.markdown(f"**{i}.**")
                    st.json(s, expanded=False)
