import os
from pathlib import Path
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv

from etb_project.ui.asset_paths import (
    asset_request_headers,
    derive_asset_path_from_stored_path,
    display_name_for_source_file,
)

load_dotenv()


SYSTEM_PROMPT = '''You are Orion, an intelligent conversational assistant for IndMex.
Your role is to help C-suite executives (CEO, CFO, COO) retrieve accurate
information from IndMex's internal data — including sales, revenue, and
financial data stored across multiple formats and systems.

---

YOUR ONLY JOB IN THIS CONVERSATION:
Understand what the executive is asking and make sure the request is
specific enough to retrieve the right data. You do NOT retrieve data
yourself. Once the request is clear, you confirm it and hand it off.

---

HOW TO BEHAVE:

1. When the user sends a question, evaluate whether it is specific enough
   to retrieve data. A good question has at least:
   - A clear TOPIC (e.g. revenue, profit margin, sales by region)
   - A TIME PERIOD (e.g. Q3 2024, last month, full year 2023)
   - A SCOPE if needed (e.g. which product line, which region, which team)

2. If the question is missing one or more of these elements, ask ONE
   clarifying question. Ask only the most important missing piece.
   Do not ask multiple questions at once.

3. If the question is already specific enough, respond with:
   - A brief confirmation of what you understood
   - A structured summary of the request labeled as:
     "READY TO RETRIEVE:" followed by the refined query in one sentence.

4. Keep your tone professional, concise, and executive-appropriate.
   No unnecessary explanations.

---

EXAMPLES OF AMBIGUOUS QUESTIONS (require follow-up):
- "How are we doing?" → Missing: topic, time period, scope
- "Show me the sales numbers" → Missing: time period, which product/region
- "What's our financial situation?" → Missing: specific metric, time period

EXAMPLES OF CLEAR QUESTIONS (ready to retrieve):
- "What was IndMex's total revenue in Q3 2024 broken down by product line?"
- "Compare net profit margin for 2023 vs 2024 across all business units."
- "What were the top 5 customers by revenue in the last fiscal year?"

---

IMPORTANT RULES:
- Never make up data or answer with numbers you don't have.
- Never ask more than one clarifying question per turn.
- Never repeat the same clarifying question twice.
- If after 2 rounds of clarification the question is still vague,
  make a reasonable assumption, state it clearly, and proceed to
  "READY TO RETRIEVE."'''


def ensure_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages: list[dict[str, str]] = []
    if "session_id" not in st.session_state:
        # Stable per-browser-session identifier; orchestrator uses it for memory.
        st.session_state.session_id = os.urandom(16).hex()
    if "last_sources" not in st.session_state:
        st.session_state.last_sources = []


def call_orchestrator_chat(message: str) -> tuple[str, list[dict]]:
    """Send a message to the Orchestrator API and return (answer, sources)."""
    base_url = os.getenv("ORCHESTRATOR_BASE_URL", "http://localhost:8001").rstrip("/")
    url = f"{base_url}/v1/chat"
    payload = {
        "session_id": st.session_state.session_id,
        "message": message,
        "return_sources": True,
    }
    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
    except requests.RequestException as exc:
        return (
            "Orion could not reach the Orchestrator service. "
            f"Please verify it is running and reachable at {base_url}. ({exc})",
            [],
        )
    data = response.json() if response.content else {}
    answer = str(data.get("answer") or "").strip()
    sources = data.get("sources") or []
    if not answer:
        answer = "Orion did not receive a valid answer from the Orchestrator."
    return answer, sources


def _orchestrator_base_url() -> str:
    return os.getenv("ORCHESTRATOR_BASE_URL", "http://localhost:8001").rstrip("/")


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
    base = _orchestrator_base_url()
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
    """Fetch image bytes via orchestrator proxy; includes auth when configured."""
    return _fetch_asset_bytes_cached(asset_path, _asset_auth_configured())


def _candidate_asset_paths_from_record(rec: dict[str, Any]) -> list[str]:
    """Ordered list of paths to try for ``/v1/assets/...``."""
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
    """Ordered candidates for single-image metadata (caption docs)."""
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

    details: list[str] = []
    if meta.get("caption_source"):
        details.append(f"caption_source: {meta.get('caption_source')}")
    if meta.get("xref"):
        details.append(f"xref: {meta.get('xref')}")
    if meta.get("image_index"):
        details.append(f"image_index: {meta.get('image_index')}")
    if details:
        st.caption(" • ".join(details))

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


def main():
    st.set_page_config(
        page_title="Orion",
        page_icon="🛰️",
        layout="centered",
    )

    st.markdown(
        """
        <style>
          :root {
            --orion-bg: #05030a;
            --orion-text: rgba(255, 255, 255, 0.98);
            --orion-muted: rgba(255, 255, 255, 0.72);
            --orion-glass: rgba(255, 255, 255, 0.07);
            --orion-border: rgba(190, 170, 255, 0.28);
            --orion-accent: rgba(140, 90, 255, 0.65);
          }

          html, body, [class*="stApp"] {
            background-color: var(--orion-bg) !important;
            color: var(--orion-text) !important;
            background-image:
              radial-gradient(circle at 50% -10%, rgba(140, 90, 255, 0.45), rgba(0,0,0,0) 55%),
              radial-gradient(circle at 15% 85%, rgba(16, 125, 255, 0.30), rgba(0,0,0,0) 55%),
              radial-gradient(circle at 90% 20%, rgba(255, 60, 220, 0.18), rgba(0,0,0,0) 60%);
            background-attachment: fixed;
          }

          .stApp {
            padding-top: 72px;
          }

          /* Center and frosted-glass style for the chat input */
          div[data-testid="stChatInput"] {
            max-width: 820px;
            margin-left: auto;
            margin-right: auto;
          }

          div[data-testid="stChatInput"] {
            padding: 10px 10px 8px 10px;
            border-radius: 22px;
            border: 1px solid rgba(255,255,255,0.12);
            background: rgba(255,255,255,0.02);
            box-shadow: 0 18px 55px rgba(0, 0, 0, 0.35);
          }

          div[data-testid="stChatInput"] textarea {
            background: rgba(140, 90, 255, 0.08) !important;
            border: 1px solid rgba(190, 170, 255, 0.35) !important;
            color: var(--orion-text) !important;
            border-radius: 18px !important;
            padding: 14px 16px !important;
            backdrop-filter: blur(12px) !important;
            -webkit-backdrop-filter: blur(12px) !important;
            box-shadow:
              inset 0 0 0 1px rgba(255,255,255,0.06),
              0 10px 30px rgba(0,0,0,0.25) !important;
          }

          div[data-testid="stChatInput"] textarea::placeholder {
            color: rgba(255, 255, 255, 0.55) !important;
          }

          /* Keep send button legible */
          div[data-testid="stChatInput"] button {
            color: var(--orion-text) !important;
          }

          /* Style quick action buttons */
          .stButton > button {
            background: rgba(255, 255, 255, 0.06) !important;
            border: 1px solid rgba(255, 255, 255, 0.18) !important;
            color: var(--orion-text) !important;
            border-radius: 999px !important;
            padding: 10px 14px !important;
            font-weight: 600 !important;
            backdrop-filter: blur(10px) !important;
            -webkit-backdrop-filter: blur(10px) !important;
          }
          .stButton > button:hover {
            background: rgba(255, 255, 255, 0.10) !important;
            border-color: rgba(255, 255, 255, 0.28) !important;
          }

          /* White text inside expander/content */
          .stMarkdown, .stText, .stCaption {
            color: var(--orion-text) !important;
          }

          .stCaption {
            color: var(--orion-muted) !important;
          }

          /* Ensure the chat area doesn't cover the background */
          div[data-testid="stVerticalBlock"],
          div.block-container,
          div[data-testid="stAppViewContainer"],
          section,
          main {
            background: transparent !important;
          }

          div[data-testid="stChatMessage"],
          div[data-testid="stChatMessageContainer"],
          div[data-testid="stChat"] {
            background: transparent !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    ensure_session_state()

    st.title("Orion")
    st.caption(
        "Executive-focused assistant that refines your data requests so they are ready for retrieval from IndMex's internal systems."
    )

    with st.expander("What Orion does", expanded=False):
        st.markdown("""
            - **Clarifies requests** from C‑suite leaders so they can be executed by downstream data systems.
            - **Does not retrieve or fabricate data**; it only structures the request.
            - Ensures each request has a **topic**, **time period**, and **scope** where needed.
            - Produces a final line starting with **`READY TO RETRIEVE:`** when the request is clear.
            """)

    # Render chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input at the bottom
    user_input = st.chat_input(
        "Describe the information you need from IndMex's data..."
    )

    if user_input:
        # Add user message to history and display it
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Orion is retrieving an answer..."):
                reply, sources = call_orchestrator_chat(user_input)
                st.markdown(reply)
                st.session_state.messages.append(
                    {"role": "assistant", "content": reply}
                )
                st.session_state.last_sources = sources or []

    # Render the most recent Sources on every rerun so
    # radio interactions don't make it disappear.
    if st.session_state.last_sources:
        with st.expander("Sources", expanded=True):
            for i, s in enumerate(st.session_state.last_sources, 1):
                if isinstance(s, dict):
                    render_source_card(i, s)
                else:
                    st.markdown(f"**{i}.**")
                    st.json(s, expanded=False)


if __name__ == "__main__":
    main()
