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


def render_admin_documents() -> None:
    st.subheader("Documents")
    base = retriever_base_url()
    idx_hdr = _retriever_index_headers()

    if not admin_api_token():
        st.warning(
            "Configure ``ETB_ADMIN_API_TOKEN`` to list, delete, or reindex. "
            "Use ``RETRIEVER_API_KEY`` for uploads when the retriever requires it."
        )

    files, err = _list_uploads(base)
    if err:
        st.error(err)
    elif files:
        st.dataframe(
            [
                {"id": f.get("id"), "name": f.get("name"), "size": f.get("size")}
                for f in files
            ],
            use_container_width=True,
        )
    else:
        st.caption("No staged PDFs in the upload directory.")

    st.markdown("#### Upload PDFs")
    if not idx_hdr:
        st.info(
            "Set ``RETRIEVER_API_KEY`` when the retriever enforces API key on indexing."
        )
    up = st.file_uploader("PDF files", type=["pdf"], accept_multiple_files=True)
    if up and st.button("Upload and index", key="btn_upload_index"):
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
                status = st.empty()
                for _ in range(120):
                    j, jerr = _poll_job(base, str(job_id))
                    if jerr:
                        status.warning(jerr)
                        break
                    stt = (j or {}).get("status", "?")
                    msg = (j or {}).get("message") or ""
                    status.info(f"Status: **{stt}** {msg}")
                    if stt in ("completed", "failed"):
                        if stt == "failed":
                            st.error((j or {}).get("error") or "Job failed.")
                        break
                    time.sleep(1)
            else:
                st.success("Index request accepted (synchronous).")
        except requests.RequestException as exc:
            st.error(format_request_error(exc))

    st.markdown("#### Delete staged file")
    del_id = st.text_input("File id (as shown in list, e.g. uuid_filename.pdf)")
    confirm_del = st.checkbox(
        "I understand this removes the staged file from disk.", key="c_del"
    )
    if st.button("Delete file", key="btn_del") and confirm_del and del_id.strip():
        safe_id = quote(del_id.strip(), safe="")
        ok, derr = delete_json(f"{base}/v1/admin/uploads/{safe_id}")
        if ok:
            st.success("Deleted.")
        else:
            st.error(derr or "Delete failed.")

    st.markdown("#### Rebuild index from uploads")
    st.caption(
        "Runs a full reindex (reset) from all PDFs currently in the upload directory."
    )
    confirm_re = st.checkbox("I understand this rebuilds the vector index.", key="c_re")
    if st.button("Reindex from uploads", key="btn_re") and confirm_re:
        data, perr = post_empty(f"{base}/v1/admin/reindex-from-uploads")
        if perr:
            st.error(perr)
        elif data and data.get("job_id"):
            jid = data["job_id"]
            st.success(f"Job `{jid}` started.")
            status = st.empty()
            for _ in range(180):
                j, jerr = _poll_job(base, str(jid))
                if jerr:
                    status.warning(jerr)
                    break
                stt = (j or {}).get("status", "?")
                status.info(f"Status: **{stt}**")
                if stt in ("completed", "failed"):
                    if stt == "failed":
                        st.error((j or {}).get("error") or "Job failed.")
                    break
                time.sleep(1)
        else:
            st.success("Reindex completed (synchronous).")
