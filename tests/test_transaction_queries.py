"""Tests for ``etb_project.transaction_queries`` (isolated temp SQLite)."""

from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from etb_project import transaction_queries

_SCHEMA = """
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


def _seed_db(db_path, *, n_rows: int = 5) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(_SCHEMA)
        for i in range(n_rows):
            conn.execute(
                """
                INSERT INTO transactions (
                    Transaction_ID, Transaction_Date, Store_Region, Product_ID,
                    Quantity_Sold, Net_Sales_Value
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    f"T{i}",
                    f"2024-01-{i + 1:02d}",
                    "West" if i % 2 == 0 else "East",
                    f"P{i % 3}",
                    1 + i,
                    float(10 * i),
                ),
            )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def isolated_tx_db(tmp_path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "tx.db"
    monkeypatch.setenv("ETB_TRANSACTION_DB", str(db))
    monkeypatch.setenv("ETB_TRANSACTION_SQL", str(tmp_path / "missing.sql"))
    monkeypatch.delenv("ETB_TRANSACTION_AUTO_BUILD_DB", raising=False)
    yield db


def test_load_transactions_respects_date_and_filters(
    isolated_tx_db, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = isolated_tx_db
    _seed_db(db, n_rows=5)
    monkeypatch.setenv("ETB_PRODUCT_CATALOG", str(tmp_path / "no_catalog.csv"))

    r = transaction_queries.load_transactions(
        start_date="2024-01-02",
        end_date="2024-01-04",
        filters={"Store_Region": ["East"]},
        limit=50,
        include_catalog=False,
    )
    assert not r.truncated
    assert r.detail is None
    df = r.dataframe
    assert len(df) == 2
    assert set(df["Transaction_ID"]) == {"T1", "T3"}


def test_load_transactions_limit_truncation(isolated_tx_db) -> None:
    _seed_db(isolated_tx_db, n_rows=5)
    r = transaction_queries.load_transactions(limit=3, include_catalog=False)
    assert r.truncated
    assert len(r.dataframe) == 3


def test_disallowed_filter_column_raises(isolated_tx_db) -> None:
    _seed_db(isolated_tx_db, n_rows=1)
    with pytest.raises(ValueError, match="not allowed"):
        transaction_queries.load_transactions(
            filters={"NotAColumn": ["x"]},
            include_catalog=False,
        )


def test_json_safe_value_nan_to_none() -> None:
    assert transaction_queries.json_safe_value(float("nan")) is None
    assert transaction_queries.json_safe_value(1.5) == 1.5
    assert transaction_queries.json_safe_value("a") == "a"


def test_dataframe_to_json_rows() -> None:
    df = pd.DataFrame({"a": [1, None], "b": [float("nan"), 2.0]})
    rows = transaction_queries.dataframe_to_json_rows(df)
    assert rows[0]["a"] == 1
    assert rows[0]["b"] is None
    assert rows[1]["a"] is None
    assert rows[1]["b"] == 2.0


def test_ensure_empty_when_no_seed(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "empty.db"
    monkeypatch.setenv("ETB_TRANSACTION_DB", str(db))
    monkeypatch.setenv("ETB_TRANSACTION_SQL", str(tmp_path / "nope.sql"))
    monkeypatch.delenv("ETB_TRANSACTION_AUTO_BUILD_DB", raising=False)
    path, detail = transaction_queries.ensure_transaction_db()
    assert path == db.resolve()
    assert detail is not None
    assert "No transaction" in detail or "empty" in detail.lower()
    r = transaction_queries.load_transactions(limit=10, include_catalog=False)
    assert len(r.dataframe) == 0


def test_sql_present_without_auto_build_creates_empty_with_detail(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "fresh.db"
    sql = tmp_path / "fresh.sql"
    sql.write_text("SELECT 1;\n", encoding="utf-8")
    monkeypatch.setenv("ETB_TRANSACTION_DB", str(db))
    monkeypatch.setenv("ETB_TRANSACTION_SQL", str(sql))
    monkeypatch.delenv("ETB_TRANSACTION_AUTO_BUILD_DB", raising=False)
    path, detail = transaction_queries.ensure_transaction_db()
    assert path.exists()
    assert detail is not None
    assert "AUTO_BUILD" in detail
