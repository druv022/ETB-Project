"""SQLite storage for hierarchical retrieval (parent pages + child chunks)."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from etb_project.document_processing.processor import HierarchicalParent
from etb_project.vectorstore.manifest import IndexManifest

HIERARCHY_SQLITE_NAME = "hierarchy.sqlite"
HIERARCHY_BACKEND_SQLITE_V1 = "sqlite_v1"
HIERARCHY_SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE parent (
  parent_id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  page_start INTEGER NOT NULL,
  page_end INTEGER NOT NULL,
  full_text TEXT NOT NULL,
  metadata_json TEXT NOT NULL
);

CREATE TABLE child (
  child_id TEXT PRIMARY KEY,
  parent_id TEXT NOT NULL REFERENCES parent(parent_id),
  chunk_index INTEGER NOT NULL,
  text TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  faiss_text_id TEXT,
  UNIQUE(parent_id, chunk_index)
);

CREATE INDEX idx_child_parent ON child(parent_id);
"""


def hierarchy_sqlite_path(vector_store_root: Path) -> Path:
    return vector_store_root / HIERARCHY_SQLITE_NAME


def hierarchy_index_usable(manifest: IndexManifest, vector_store_root: Path) -> bool:
    """True when manifest declares hierarchy v1 and ``hierarchy.sqlite`` exists."""
    if manifest.hierarchy_schema_version != HIERARCHY_SCHEMA_VERSION:
        return False
    if manifest.hierarchy_backend != HIERARCHY_BACKEND_SQLITE_V1:
        return False
    return hierarchy_sqlite_path(vector_store_root).is_file()


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    conn.commit()


def replace_all_hierarchy(
    db_path: Path,
    parents: Sequence[HierarchicalParent],
    child_docs: Sequence[Document],
) -> None:
    """Replace the hierarchy DB with the given parents and child documents."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    try:
        init_schema(conn)
        append_parents_and_children(conn, parents, child_docs)
    finally:
        conn.close()


def append_parents_and_children(
    conn: sqlite3.Connection,
    parents: Sequence[HierarchicalParent],
    child_docs: Sequence[Document],
) -> None:
    for p in parents:
        conn.execute(
            "INSERT OR REPLACE INTO parent (parent_id, source, page_start, page_end, full_text, metadata_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                p.parent_id,
                p.source,
                p.page_start,
                p.page_end,
                p.full_text,
                json.dumps(dict(p.metadata), ensure_ascii=False),
            ),
        )
    for doc in child_docs:
        meta = dict(doc.metadata or {})
        child_id = str(meta.get("child_id") or "")
        parent_id = str(meta.get("parent_id") or "")
        chunk_index = int(meta.get("chunk_index", 0))
        if not child_id or not parent_id:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO child (child_id, parent_id, chunk_index, text, metadata_json, faiss_text_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                child_id,
                parent_id,
                chunk_index,
                doc.page_content,
                json.dumps(meta, ensure_ascii=False),
                meta.get("faiss_text_id"),
            ),
        )
    conn.commit()


def get_parents_ordered(
    db_path: Path,
    parent_ids: list[str],
) -> list[tuple[str, str, dict[str, Any]]]:
    """Return ``(parent_id, full_text, metadata_dict)`` in the order of ``parent_ids`` (first wins)."""
    if not parent_ids or not db_path.is_file():
        return []
    conn = sqlite3.connect(str(db_path))
    try:
        unique: list[str] = []
        seen: set[str] = set()
        for pid in parent_ids:
            if pid in seen:
                continue
            seen.add(pid)
            unique.append(pid)
        if not unique:
            return []
        rows: dict[str, tuple[str, dict[str, Any]]] = {}
        for pid in unique:
            cur = conn.execute(
                "SELECT parent_id, full_text, metadata_json FROM parent WHERE parent_id = ?",
                (pid,),
            )
            r = cur.fetchone()
            if r:
                rows[str(r[0])] = (str(r[1]), json.loads(r[2]))
        out: list[tuple[str, str, dict[str, Any]]] = []
        for pid in unique:
            if pid in rows:
                ft, md = rows[pid]
                out.append((pid, ft, md))
        return out
    finally:
        conn.close()


def expand_child_hits_to_parents(
    ranked_children: list[Document],
    db_path: Path,
    *,
    max_parents: int,
    max_total_chars: int,
) -> list[Document]:
    """Expand child hits to parent bodies; interleave non-parent docs (e.g. captions); apply caps.

    For each document with ``parent_id``, the first occurrence emits one parent ``Document``;
    later hits sharing the same parent are skipped. Documents without ``parent_id`` pass through.
    """
    if not ranked_children or not db_path.is_file():
        return ranked_children

    ordered_pids: list[str] = []
    seen_discover: set[str] = set()
    for doc in ranked_children:
        pid = (doc.metadata or {}).get("parent_id")
        if isinstance(pid, str) and pid and pid not in seen_discover:
            seen_discover.add(pid)
            ordered_pids.append(pid)

    if not ordered_pids:
        return ranked_children

    parents_map: dict[str, tuple[str, dict[str, Any]]] = {}
    for parent_id, full_text, pmeta in get_parents_ordered(db_path, ordered_pids):
        parents_map[parent_id] = (full_text, pmeta)

    out: list[Document] = []
    seen_parents: set[str] = set()
    parent_bodies = 0
    total_parent_chars = 0

    for doc in ranked_children:
        pid = (doc.metadata or {}).get("parent_id")
        if isinstance(pid, str) and pid:
            if pid in seen_parents:
                continue
            if parent_bodies >= max_parents:
                continue
            row = parents_map.get(pid)
            if row is None:
                out.append(doc)
                continue
            full_text, pmeta = row
            remaining = max_total_chars - total_parent_chars
            if remaining <= 0:
                continue
            body = full_text if len(full_text) <= remaining else full_text[:remaining]
            total_parent_chars += len(body)
            seen_parents.add(pid)
            parent_bodies += 1
            meta = dict(pmeta)
            meta["parent_id"] = pid
            meta["hierarchy_expanded"] = True
            out.append(Document(page_content=body, metadata=meta))
        else:
            out.append(doc)

    return out if out else ranked_children
