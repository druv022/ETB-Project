"""
Data access helpers for the synthetic retail transaction database.

This module is responsible for:
- Establishing a connection to a SQLite database that holds the
  `transactions` table generated from `transaction_database_5yrs_full.sql`.
- Providing convenience functions to load and aggregate transactions
  into pandas DataFrames for downstream reporting modules.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

Metric = Literal["revenue", "units", "transactions"]


@dataclass(frozen=True)
class DBConfig:
    """Configuration for locating and using the transaction database."""

    db_path: Path


def default_db_config() -> DBConfig:
    """
    Return the default DB configuration for the tools workspace.

    By default this points at a SQLite database created alongside the
    generated SQL file under `tools/data_generation/Transaction_data`.
    """

    project_root = Path(__file__).resolve().parents[3]
    data_dir = project_root / "tools" / "data_generation" / "Transaction_data"
    db_path = data_dir / "transaction_database_5yrs_full.db"
    return DBConfig(db_path=db_path)


def ensure_sqlite_db(config: DBConfig | None = None) -> Path:
    """
    Ensure a SQLite DB exists, creating it from the large .sql file if needed.

    This function is intentionally simple and synchronous because it is only
    expected to run occasionally (e.g. the first time reports are generated).
    """

    cfg = config or default_db_config()
    if cfg.db_path.exists():
        return cfg.db_path

    sql_file = cfg.db_path.with_suffix(".sql")
    if not sql_file.exists():
        raise FileNotFoundError(
            f"Expected SQL file not found at {sql_file}. "
            "Generate it first with the transaction data tools."
        )

    conn = sqlite3.connect(cfg.db_path)
    try:
        with sql_file.open("r", encoding="utf-8") as f:
            script = f.read()
        conn.executescript(script)
        conn.commit()
    finally:
        conn.close()

    return cfg.db_path


def connect(config: DBConfig | None = None) -> sqlite3.Connection:
    """Return a SQLite connection to the transaction database, creating it if needed."""

    db_path = ensure_sqlite_db(config)
    return sqlite3.connect(db_path)


def load_transactions(
    start_date: str | None = None,
    end_date: str | None = None,
    filters: Mapping[str, Iterable[object]] | None = None,
    config: DBConfig | None = None,
) -> pd.DataFrame:
    """
    Load transactions into a DataFrame, optionally filtered by date range and dimensions.

    Dates are expected in ISO format (YYYY-MM-DD). Filters is a mapping from
    column name to a list/iterable of allowed values (IN filter).
    """

    conn = connect(config)
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

        if filters:
            for col, values in filters.items():
                values_list = list(values)
                if not values_list:
                    continue
                placeholders = ",".join("?" for _ in values_list)
                where_clauses.append(f"{col} IN ({placeholders})")
                params.extend(values_list)

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        df = pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()

    return df


def aggregate_transactions(
    df: pd.DataFrame,
    group_by_cols: list[str],
    metrics: Iterable[Metric],
) -> pd.DataFrame:
    """
    Aggregate transaction-level data into higher-level metrics.

    Supported metrics:
    - 'revenue': sum of Net_Sales_Value
    - 'units': sum of Quantity_Sold
    - 'transactions': count of distinct Transaction_ID
    """

    agg_spec: dict[str, tuple[str, str]] = {}

    if "revenue" in metrics:
        agg_spec["revenue"] = ("Net_Sales_Value", "sum")
    if "units" in metrics:
        agg_spec["units"] = ("Quantity_Sold", "sum")
    if "transactions" in metrics:
        agg_spec["transactions"] = ("Transaction_ID", "nunique")

    if not agg_spec:
        raise ValueError("At least one metric is required for aggregation.")

    grouped = df.groupby(group_by_cols).agg(**agg_spec).reset_index()
    return grouped
