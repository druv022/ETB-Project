"""Reconciliation report between source retail CSV and expected monthly rollups.

Compares ``Ed_Data/walmart_retail_sales_database.csv`` against definitions in
``transaction_database_5yrs_full.sql`` (or alternate SQL name) and writes
``reconciliation_report.csv`` plus a text summary. Used to validate synthetic
data consistency—not imported by the main app.
"""

import csv
import os
from decimal import Decimal, getcontext

getcontext().prec = 28  # high precision for money math


def format_decimal(val: Decimal) -> str:
    return f"{val:.2f}"


def main():
    root = os.path.dirname(os.path.abspath(__file__))

    # Adjust these names if yours differ
    source_path = os.path.join(root, "Ed_Data", "walmart_retail_sales_database.csv")
    sql_path = os.path.join(
        root, "transaction_database_5yrs_full.sql"
    )  # or "transactions_database.sql"
    recon_path = os.path.join(root, "reconciliation_report.csv")
    recon_summary_path = os.path.join(root, "reconciliation_summary_full.txt")

    print("Loading source data...")
    with open(source_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        source_rows = list(reader)

    # Build base reconciliation dict from source CSV
    # key: (product_id, year, month)
    recon = {}

    for row in source_rows:
        product_id = int(row["Product_ID"])
        year = int(row["Year"])
        month = int(row["Month"])
        key = (product_id, year, month)

        if key not in recon:
            recon[key] = {
                "Product_ID": product_id,
                "Year": year,
                "Month": month,
                "MonthlyUnits": int(row["Units_Sold"]),
                "MonthlySales": Decimal(row["Total_Sales_Value"]),
                "TxnUnits": 0,
                "TxnSales": Decimal("0.0"),
            }

    print("Parsing SQL inserts...")
    # Aggregate from SQL INSERT statements
    with open(sql_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("INSERT INTO"):
                continue

            values_idx = line.find("VALUES (")
            if values_idx < 0:
                continue

            # Extract the portion after "VALUES (", strip trailing ");"
            values_part = line[values_idx + len("VALUES (") :].rstrip(");")
            parts = values_part.split(",")

            if len(parts) < 20:
                continue

            # Match PS1 indexes:
            # parts[2] = 'YYYY-MM-DD', parts[9] = Product_ID,
            # parts[11] = Quantity_Sold, parts[16] = Net_Sales_Value
            date_text = parts[2].strip().strip("'").strip('"')
            year = int(date_text[0:4])
            month = int(date_text[5:7])

            product_id = int(parts[9])
            qty = int(parts[11])
            net = Decimal(parts[16])

            key = (product_id, year, month)
            if key not in recon:
                # If not present in source, create with zeros for monthly fields
                recon[key] = {
                    "Product_ID": product_id,
                    "Year": year,
                    "Month": month,
                    "MonthlyUnits": 0,
                    "MonthlySales": Decimal("0.0"),
                    "TxnUnits": 0,
                    "TxnSales": Decimal("0.0"),
                }

            recon[key]["TxnUnits"] += qty
            recon[key]["TxnSales"] += net

    print("Writing reconciliation report...")
    with open(recon_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Product_ID",
                "Year",
                "Month",
                "MonthlyUnits",
                "TxnUnitsSum",
                "UnitsMatch",
                "MonthlySales",
                "TxnNetSalesSum",
                "SalesDiff",
                "SalesDiffPct",
            ]
        )

        unit_mismatch_count = 0
        sales_diffs = []

        # Sort by Year, Month, Product_ID
        for product_id, year, month in sorted(
            recon.keys(), key=lambda k: (k[1], k[2], k[0])
        ):
            r = recon[(product_id, year, month)]
            units_match = r["MonthlyUnits"] == r["TxnUnits"]
            if not units_match:
                unit_mismatch_count += 1

            sales_diff = r["TxnSales"] - r["MonthlySales"]
            if r["MonthlySales"] != 0:
                sales_diff_pct = float(
                    (sales_diff / r["MonthlySales"]) * Decimal("100")
                )
            else:
                sales_diff_pct = 0.0

            sales_diffs.append(sales_diff.copy_abs())

            writer.writerow(
                [
                    r["Product_ID"],
                    r["Year"],
                    r["Month"],
                    r["MonthlyUnits"],
                    r["TxnUnits"],
                    units_match,
                    format_decimal(r["MonthlySales"]),
                    format_decimal(r["TxnSales"]),
                    format_decimal(sales_diff),
                    round(sales_diff_pct, 4),
                ]
            )

    # Summary stats
    if sales_diffs:
        max_diff = max(d for d in sales_diffs)
        mean_diff = sum(sales_diffs) / Decimal(len(sales_diffs))
    else:
        max_diff = Decimal("0.0")
        mean_diff = Decimal("0.0")

    summary_lines = [
        f"Unit mismatches: {unit_mismatch_count}",
        f"Max absolute sales diff: {format_decimal(max_diff)}",
        f"Mean absolute sales diff: {format_decimal(mean_diff)}",
    ]

    with open(recon_summary_path, "w", encoding="utf-8") as f:
        for line in summary_lines:
            f.write(line + "\n")

    print("Done.")
    print(f"Recon report: {recon_path}")
    print(f"Recon summary: {recon_summary_path}")


if __name__ == "__main__":
    main()
