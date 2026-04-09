"""Safe SQLite access to the synthetic ``transactions`` table (app / API layer).

Aligned with ``tools/data_generation/report_generation/data_access.py`` but lives
under ``etb_project`` so callers do not import ``tools/`` at runtime.

Paths are resolved from the project root (parent of ``src/``). Override with
``ETB_TRANSACTION_DB``, ``ETB_TRANSACTION_SQL``, ``ETB_PRODUCT_CATALOG``.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DB_RELATIVE = Path("data") / "transaction_database_5yrs_full.db"
DEFAULT_CATALOG_RELATIVE = (
    Path("tools")
    / "data_generation"
    / "Transaction_data"
    / "Ed_Data"
    / "PRODUCT_CATALOG.csv"
)

DEFAULT_QUERY_LIMIT = 500
MAX_QUERY_LIMIT = 2000

ALLOWED_FILTER_COLUMNS: frozenset[str] = frozenset(
    {
        "Transaction_ID",
        "Transaction_Date",
        "Transaction_Time",
        "Store_ID",
        "Store_Region",
        "Order_Channel",
        "Customer_ID",
        "Customer_Type",
        "Product_ID",
        "SKU",
    }
)

_CREATE_TRANSACTIONS_SQL = """
CREATE TABLE IF NOT EXISTS transactions (
    Transaction_ID TEXT,
    Transaction_Date TEXT,
    Transaction_Time TEXT,
    Store_ID TEXT,
    Store_Region TEXT,
    Order_Channel TEXT,
    Customer_ID TEXT,
    Customer_Type TEXT,
    Product_ID TEXT,
    SKU TEXT,
    Quantity_Sold INTEGER,
    Gross_Sales_Value REAL,
    Discount_Amount REAL,
    "Discount_%" REAL,
    Net_Sales_Value REAL,
    Tax_amount REAL,
    Total_Value REAL
);
"""


def _env_truthy(name: str, default: bool = False) -> bool:
    v = os.environ.get(name, "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


def _resolve_project_path(raw: str | None, default_relative: Path) -> Path:
    if not raw or not raw.strip():
        return (PROJECT_ROOT / default_relative).resolve()
    p = Path(raw.strip()).expanduser()
    if p.is_absolute():
        return p.resolve()
    return (PROJECT_ROOT / p).resolve()


def transaction_db_path() -> Path:
    return _resolve_project_path(
        os.environ.get("ETB_TRANSACTION_DB"), DEFAULT_DB_RELATIVE
    )


def transaction_sql_path() -> Path:
    env_sql = os.environ.get("ETB_TRANSACTION_SQL", "").strip()
    if env_sql:
        return _resolve_project_path(env_sql, DEFAULT_DB_RELATIVE)
    return transaction_db_path().with_suffix(".sql")


def product_catalog_path() -> Path:
    return _resolve_project_path(
        os.environ.get("ETB_PRODUCT_CATALOG"), DEFAULT_CATALOG_RELATIVE
    )


def _ensure_transactions_table(conn: sqlite3.Connection) -> None:
    conn.executescript(_CREATE_TRANSACTIONS_SQL)


def ensure_transaction_db() -> tuple[Path, str | None]:
    """Create or locate the SQLite DB; return ``(path, detail)``.

    ``detail`` is non-None when the database has no imported seed data and the
    caller may need to pre-build the DB or set ``ETB_TRANSACTION_AUTO_BUILD_DB``.
    """
    db_path = transaction_db_path()
    sql_path = transaction_sql_path()
    auto_build = _env_truthy("ETB_TRANSACTION_AUTO_BUILD_DB", default=False)
    detail: str | None = None

    if db_path.exists():
        conn = sqlite3.connect(db_path)
        try:
            _ensure_transactions_table(conn)
            conn.commit()
        finally:
            conn.close()
        return db_path, detail

    db_path.parent.mkdir(parents=True, exist_ok=True)

    if sql_path.exists() and auto_build:
        conn = sqlite3.connect(db_path)
        try:
            with sql_path.open("r", encoding="utf-8") as f:
                script = f.read()
            conn.executescript(script)
            _ensure_transactions_table(conn)
            conn.commit()
        finally:
            conn.close()
        return db_path, detail

    if sql_path.exists() and not auto_build:
        conn = sqlite3.connect(db_path)
        try:
            _ensure_transactions_table(conn)
            conn.commit()
        finally:
            conn.close()
        detail = (
            "Seed SQL exists but ETB_TRANSACTION_AUTO_BUILD_DB is not enabled; "
            "created an empty transactions table. Pre-build the .db offline or set "
            "ETB_TRANSACTION_AUTO_BUILD_DB=1 to import from SQL (slow)."
        )
        return db_path, detail

    conn = sqlite3.connect(db_path)
    try:
        _ensure_transactions_table(conn)
        conn.commit()
    finally:
        conn.close()
    detail = "No transaction .db or seed .sql found; using empty transactions table."
    return db_path, detail


@dataclass(frozen=True)
class TransactionLoadResult:
    """Result of a bounded ``transactions`` query."""

    dataframe: pd.DataFrame
    detail: str | None
    truncated: bool


def _normalize_filters(
    filters: Mapping[str, Iterable[object]] | None,
) -> dict[str, list[object]]:
    if not filters:
        return {}
    out: dict[str, list[object]] = {}
    for col, values in filters.items():
        if col not in ALLOWED_FILTER_COLUMNS:
            raise ValueError(f"Filter column not allowed: {col!r}")
        vals = list(values)
        if vals:
            out[col] = vals
    return out


def load_transactions(
    start_date: str | None = None,
    end_date: str | None = None,
    filters: Mapping[str, Iterable[object]] | None = None,
    *,
    limit: int = DEFAULT_QUERY_LIMIT,
    include_catalog: bool = True,
) -> TransactionLoadResult:
    """Load up to ``limit`` rows (plus one internal probe for truncation)."""
    if limit < 1:
        raise ValueError("limit must be >= 1")
    if limit > MAX_QUERY_LIMIT:
        limit = MAX_QUERY_LIMIT

    db_path, ensure_detail = ensure_transaction_db()
    normalized = _normalize_filters(filters)
    fetch_cap = limit + 1

    conn = sqlite3.connect(db_path)
    try:
        query = "SELECT * FROM transactions"
        where_clauses: list[str] = []
        params: list[object] = []

        if start_date is not None:
            where_clauses.append("Transaction_Date >= ?")
            params.append(start_date)
        if end_date is not None:
            where_clauses.append("Transaction_Date <= ?")
            params.append(end_date)

        for col, values_list in normalized.items():
            placeholders = ",".join("?" for _ in values_list)
            where_clauses.append(f"{col} IN ({placeholders})")
            params.extend(values_list)

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        query += f" LIMIT {fetch_cap}"
        df = pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()

    truncated = len(df) > limit
    if truncated:
        df = df.iloc[:limit].copy()

    if include_catalog and "Category" not in df.columns and "Product_ID" in df.columns:
        cat_path = product_catalog_path()
        if cat_path.exists():
            catalog = pd.read_csv(cat_path)[["Product_ID", "Category"]].copy()
            df = df.merge(catalog, on="Product_ID", how="left")

    return TransactionLoadResult(
        dataframe=df,
        detail=ensure_detail,
        truncated=truncated,
    )


def json_safe_value(v: Any) -> Any:
    """Convert a cell value to JSON-serializable form."""
    if v is None:
        return None
    if isinstance(v, (str, int, bool)):
        return v
    if isinstance(v, float):
        if pd.isna(v) or np.isnan(v):
            return None
        return v
    if isinstance(v, (np.generic,)):
        return json_safe_value(v.item())
    if pd.isna(v):
        return None
    if hasattr(v, "isoformat"):
        try:
            return v.isoformat()
        except Exception:
            return str(v)
    return str(v)


def dataframe_to_json_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a DataFrame to a list of JSON-safe dict records."""
    records = cast(list[dict[str, Any]], df.to_dict(orient="records"))
    for rec in records:
        for key in list(rec.keys()):
            rec[key] = json_safe_value(rec.get(key))
    return records
