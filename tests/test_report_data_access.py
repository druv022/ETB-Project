import pandas as pd

from tools.data_generation.report_generation import data_access


def test_aggregate_transactions_basic() -> None:
    df = pd.DataFrame(
        {
            "Store_ID": [1, 1, 2],
            "Net_Sales_Value": [10.0, 20.0, 30.0],
            "Quantity_Sold": [1, 2, 3],
            "Transaction_ID": ["A", "B", "C"],
        }
    )
    grouped = data_access.aggregate_transactions(
        df, ["Store_ID"], ["revenue", "units", "transactions"]
    )
    assert set(grouped.columns) == {"Store_ID", "revenue", "units", "transactions"}
    row1 = grouped[grouped["Store_ID"] == 1].iloc[0]
    assert row1["revenue"] == 30.0
    assert row1["units"] == 3
    assert row1["transactions"] == 2


def test_default_db_config_points_to_transaction_data_dir() -> None:
    cfg = data_access.default_db_config()
    # The DB path should live under the Transaction_data directory
    assert "Transaction_data" in str(cfg.db_path)
