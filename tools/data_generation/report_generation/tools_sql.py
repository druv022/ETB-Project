"""
SQL-oriented helpers for the reporting workflow.

These utilities are intentionally simple and deterministic: they build
parameterised queries against the `transactions` table and execute them
using the same SQLite database used elsewhere in the data generation
tools.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from . import data_access


@dataclass(frozen=True)
class SQLQuery:
    """Container for a parametrised SQL query."""

    text: str
    params: Mapping[str, Any]


def generate_sql_query(
    category: str,
    period_start: date,
    period_end: date,
    dimensions: tuple[str, ...] | None = None,
    metrics: tuple[str, ...] | None = None,
) -> SQLQuery:
    """
    Generate a simple parametrised SQL query for the requested category.

    For now all categories share the same base WHERE clause on
    `Transaction_Date`, and the dimensions/metrics hints are present for
    future extension.
    """

    _ = category, dimensions, metrics  # reserved for future use

    sql = (
        "SELECT * FROM transactions "
        "WHERE Transaction_Date >= :start_date "
        "AND Transaction_Date <= :end_date"
    )
    params: dict[str, Any] = {
        "start_date": period_start.isoformat(),
        "end_date": period_end.isoformat(),
    }
    return SQLQuery(text=sql, params=params)


def execute_sql(query: SQLQuery) -> pd.DataFrame:
    """
    Execute a parametrised SQL query against the reporting SQLite database.

    The connection location is resolved via `data_access.default_db_config()`.
    """

    conn = data_access.connect()
    try:
        df = pd.read_sql_query(query.text, conn, params=query.params)
    finally:
        conn.close()
    return df
