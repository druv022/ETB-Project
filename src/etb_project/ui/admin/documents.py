"""Admin: staged PDFs — list, upload, delete, reindex."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote

import requests
import streamlit as st

from etb_project.ui.admin.http_helpers import (
    admin_bearer_headers,
    delete_json,
    format_request_error,
    post_empty,
)
from etb_project.ui.auth_credentials import (
    admin_api_token,
    retriever_api_key,
    retriever_base_url,
)


def _retriever_index_headers() -> dict[str, str]:
    k = retriever_api_key()
    if not k:
        return {}
    return {"Authorization": f"Bearer {k}"}


def _list_uploads(base: str) -> tuple[list[dict[str, Any]], str | None]:
    if not admin_api_token():
        return [], "Set ``ETB_ADMIN_API_TOKEN`` for document admin APIs."
    try:
        r = requests.get(
            f"{base}/v1/admin/uploads",
            headers=admin_bearer_headers(),
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        return list(data.get("files") or []), None
    except requests.RequestException as exc:
        return [], format_request_error(exc)


def _poll_job(base: str, job_id: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        r = requests.get(
            f"{base}/v1/jobs/{job_id}",
            headers=_retriever_index_headers(),
            timeout=30,
        )
        r.raise_for_status()
        return r.json(), None
    except requests.RequestException as exc:
        return None, format_request_error(exc)


def _format_size(size: Any) -> str:
    try:
        n = int(size)
    except (TypeError, ValueError):
        return "—"
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / (1024 * 1024 * 1024):.2f} GB"


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


def _subsection(title: str, subtitle: str, icon: str = "") -> None:
    st.markdown(
        f'<div style="margin:1.4rem 0 0.7rem 0;">'
        f'<div style="font-size:1.15rem;font-weight:600;color:#ffffff;'
        f'display:flex;align-items:center;gap:0.5rem;">'
        f'<span style="font-size:1.15rem;">{icon}</span>{title}</div>'
        f'<div style="font-size:0.82rem;color:rgba(219,210,250,0.55);'
        f'margin-top:0.15rem;">{subtitle}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _banner(kind: str, message: str) -> None:
    palette = {
        "warn": ("#facc15", "rgba(250,204,21,0.08)", "rgba(250,204,21,0.30)"),
        "info": ("#60a5fa", "rgba(96,165,250,0.08)", "rgba(96,165,250,0.28)"),
        "error": ("#f87171", "rgba(248,113,113,0.08)", "rgba(248,113,113,0.35)"),
        "success": ("#4ade80", "rgba(74,222,128,0.08)", "rgba(74,222,128,0.32)"),
    }
    fg, bg, border = palette.get(kind, palette["info"])
    st.markdown(
        f'<div style="padding:0.85rem 1rem;border-radius:12px;margin:0.4rem 0 0.6rem 0;'
        f'background:{bg};border:1px solid {border};color:{fg};'
        f'font-size:0.88rem;line-height:1.45;">{message}</div>',
        unsafe_allow_html=True,
    )


def _pill(label: str, color: str) -> str:
    return (
        f'<span style="display:inline-flex;align-items:center;gap:0.35rem;'
        f'padding:0.28rem 0.72rem;border-radius:999px;'
        f'background:{color}1a;border:1px solid {color}55;'
        f'color:{color};font-size:0.78rem;font-weight:600;">{label}</span>'
    )


def _render_summary(files: list[dict[str, Any]]) -> None:
    total_bytes = 0
    for f in files:
        try:
            total_bytes += int(f.get("size") or 0)
        except (TypeError, ValueError):
            pass
    st.markdown(
        '<div style="display:flex;gap:0.6rem;flex-wrap:wrap;margin:0.5rem 0 1rem 0;">'
        f'{_pill(f"{len(files)} PDFs staged", "#60a5fa")}'
        f'{_pill(f"{_format_size(total_bytes)} total", "#a78bfa")}'
        '</div>',
        unsafe_allow_html=True,
    )


def _render_file_table(files: list[dict[str, Any]]) -> None:
    rows = [
        {
            "ID": f.get("id") or "",
            "Name": f.get("name") or "",
            "Size": _format_size(f.get("size")),
        }
        for f in files
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _poll_job_ui(base: str, job_id: str, iterations: int, label: str) -> None:
    status_box = st.empty()
    for _ in range(iterations):
        j, jerr = _poll_job(base, job_id)
        if jerr:
            status_box.warning(jerr)
            return
        stt = (j or {}).get("status", "?")
        msg = (j or {}).get("message") or ""
        status_box.info(f"**{label}:** `{stt}` {msg}")
        if stt in ("completed", "failed"):
            if stt == "failed":
                st.error((j or {}).get("error") or "Job failed.")
            else:
                st.success(f"{label} finished successfully.")
            return
        time.sleep(1)


def render_admin_documents() -> None:
    _section_header(
        "Documents",
        "Manage the staged PDF corpus: upload, list, delete, and rebuild the vector index.",
    )

    base = retriever_base_url()
    idx_hdr = _retriever_index_headers()

    if not admin_api_token():
        _banner(
            "warn",
            "Configure <code>ETB_ADMIN_API_TOKEN</code> to list, delete, or reindex. "
            "Use <code>RETRIEVER_API_KEY</code> for uploads when the retriever requires it.",
        )

    _subsection(
        "Staged PDFs",
        "Files currently available in the retriever upload directory.",
    )

    files, err = _list_uploads(base)
    if err:
        _banner("error", err)
    elif files:
        _render_summary(files)
        _render_file_table(files)
    else:
        _banner("info", "No staged PDFs in the upload directory.")

    _subsection(
        "Upload PDFs",
        "Add new PDFs and trigger indexing into the vector store.",
    )
    if not idx_hdr:
        _banner(
            "info",
            "Set <code>RETRIEVER_API_KEY</code> when the retriever enforces API key on indexing.",
        )
    up = st.file_uploader(
        "Drag & drop or browse to select PDF files",
        type=["pdf"],
        accept_multiple_files=True,
    )
    if up:
        st.caption(f"{len(up)} file(s) selected · ready to upload")
    if up and st.button("Upload and index", key="btn_upload_index", type="primary"):
        file_tuples = []
        for uf in up:
            raw = uf.getvalue()
            file_tuples.append(("files", (uf.name, raw, "application/pdf")))
        try:
            with st.spinner("Uploading…"):
                r = requests.post(
                    f"{base}/v1/index/documents",
                    files=file_tuples,
                    headers=idx_hdr,
                    params={"async_mode": "true"},
                    timeout=120,
                )
            r.raise_for_status()
            data = r.json()
            job_id = data.get("job_id")
            if job_id:
                st.success(f"Job started: `{job_id}`")
                _poll_job_ui(base, str(job_id), 120, "Indexing")
            else:
                st.success("Index request accepted (synchronous).")
        except requests.RequestException as exc:
            st.error(format_request_error(exc))

    _subsection(
        "Delete staged file",
        "Permanently remove a PDF from the upload directory. This action cannot be undone.",
    )
    del_cols = st.columns([3, 2], gap="medium", vertical_alignment="bottom")
    with del_cols[0]:
        del_id = st.text_input(
            "File id",
            placeholder="e.g. 3f2a…_report.pdf",
            help="Use the ID shown in the Staged PDFs table above.",
        )
    with del_cols[1]:
        confirm_del = st.checkbox(
            "I understand this removes the file from disk.",
            key="c_del",
        )
    if st.button("Delete file", key="btn_del", disabled=not (confirm_del and del_id.strip())):
        safe_id = quote(del_id.strip(), safe="")
        ok, derr = delete_json(f"{base}/v1/admin/uploads/{safe_id}")
        if ok:
            _banner("success", "File deleted successfully.")
        else:
            _banner("error", derr or "Delete failed.")

    _subsection(
        "Rebuild index",
        "Run a full reindex from every PDF currently staged. Existing vectors are replaced.",
    )
    confirm_re = st.checkbox(
        "I understand this rebuilds the vector index from scratch.",
        key="c_re",
    )
    if st.button("Reindex from uploads", key="btn_re", disabled=not confirm_re):
        data, perr = post_empty(f"{base}/v1/admin/reindex-from-uploads")
        if perr:
            _banner("error", perr)
        elif data and data.get("job_id"):
            jid = data["job_id"]
            st.success(f"Job `{jid}` started.")
            _poll_job_ui(base, str(jid), 180, "Reindexing")
        else:
            _banner("success", "Reindex completed (synchronous).")
