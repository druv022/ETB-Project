import csv
import os
import random
import sqlite3
from datetime import datetime


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    source_path = os.path.join(root, "Ed_Data", "walmart_retail_sales_database.csv")
    db_path = os.path.join(root, "transactions.db")
    sql_path = os.path.join(root, "transaction_database_5yrs_full.sql")
    csv_path = os.path.join(root, "transactions_JanFeb_2020.csv")

    if os.path.exists(db_path):
        os.remove(db_path)

    print("Loading source data...")
    with open(source_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        source_rows = list(reader)

    print("Building product map...")
    product_map: dict[int, dict[str, object]] = {}
    categories: dict[str, float] = {}
    rng = random.Random(42)

    for row in source_rows:
        prod_id = int(row["Product_ID"])
        if prod_id <= 200 and prod_id not in product_map:
            product_map[prod_id] = {
                "SKU": str(row["SKU"]),
                "Category": str(row["Category"]),
                "UnitPrice": float(row["Unit_Price"]),
            }
            if row["Category"] not in categories:
                categories[row["Category"]] = round(0.02 + (rng.random() * 0.03), 4)

    print(f"Loaded {len(product_map)} products with {len(categories)} categories")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE transactions (
            Line_item_ID INTEGER,
            Transaction_ID TEXT,
            Transaction_Date TEXT,
            Transaction_Time TEXT,
            Store_ID INTEGER,
            Store_Region TEXT,
            Order_Channel TEXT,
            Customer_ID INTEGER,
            Customer_Type TEXT,
            Product_ID INTEGER,
            SKU TEXT,
            Quantity_Sold INTEGER,
            Unit_Selling_Price REAL,
            Gross_Sales_Value REAL,
            Discount_% REAL,
            Discount_Amount REAL,
            Net_Sales_Value REAL,
            Tax_amount REAL,
            Total_Value REAL,
            Payment_Method TEXT
        )
        """)

    store_regions = [
        "Lafayette",
        "Kokomo",
        "Naperville",
        "Indianapolis",
        "Fort Wayne",
        "South Bend",
        "Bloomington",
        "Terre Haute",
        "Muncie",
        "Evansville",
        "Carmel",
        "Fishers",
        "Noblesville",
        "Greenwood",
        "Columbus",
        "West Lafayette",
        "Gary",
        "Hammond",
        "Merrillville",
        "Valparaiso",
        "Michigan City",
        "Crown Point",
        "Portage",
        "Hobart",
        "Schererville",
        "Dyer",
        "Munster",
        "Highland",
        "Griffith",
        "La Porte",
        "Elkhart",
        "Mishawaka",
        "Goshen",
        "Warsaw",
        "Logansport",
        "Anderson",
        "Richmond",
        "New Castle",
        "Marion",
        "Vincennes",
        "Jasper",
        "Washington",
        "Shelbyville",
        "Franklin",
        "Lebanon",
        "Plainfield",
        "Avon",
        "Brownsburg",
        "Zionsville",
        "Mooresville",
        "Danville",
        "Crawfordsville",
        "Frankfort",
        "Tipton",
        "Peru",
        "Wabash",
        "Huntington",
        "Kendallville",
        "Auburn",
        "Decatur",
        "Bluffton",
        "Angola",
        "Plymouth",
        "Nappanee",
        "Monticello",
        "Rensselaer",
        "DeMotte",
        "Cedar Lake",
        "Lowell",
        "Chesterton",
        "Porter",
        "Beverly Shores",
        "Kankakee",
        "Joliet",
        "Aurora",
        "Elgin",
        "Waukegan",
        "Evanston",
        "Oak Park",
        "Schaumburg",
        "Arlington Heights",
        "Skokie",
        "Des Plaines",
        "Palatine",
        "Wheaton",
        "Downers Grove",
        "Bolingbrook",
        "Romeoville",
        "Peoria",
        "Springfield",
        "Champaign",
        "Normal",
        "Decatur IL",
        "Rockford",
        "Madison",
        "Milwaukee",
        "Green Bay",
        "Appleton",
        "Oshkosh",
        "Kenosha",
        "Racine",
        "Duluth",
        "Rochester MN",
        "St. Cloud",
        "Sioux Falls",
        "Fargo",
        "Bismarck",
    ]

    print("Generating transactions...")

    line_id = 1
    txn_counter_year: dict[int, int] = {}
    csv_lines: list[str] = []
    batch_size = 1000
    processed = 0

    # CSV header
    with open(csv_path, "w", encoding="utf-8") as csv_file:
        csv_file.write(
            "Line_item_ID,Transaction_ID,Transaction_Date,Transaction_Time,"
            "Store_ID,Store_Region,Order_Channel,Customer_ID,Customer_Type,"
            "Product_ID,SKU,Quantity_Sold,Unit_Selling_Price,Gross_Sales_Value,"
            "Discount_%,Discount_Amount,Net_Sales_Value,Tax_amount,Total_Value,"
            "Payment_Method\n"
        )

    # Group by (Year, Month)
    month_groups: dict[tuple[int, int], list[dict[str, str]]] = {}
    for row in source_rows:
        year = int(row["Year"])
        month = int(row["Month"])
        key = (year, month)
        month_groups.setdefault(key, []).append(row)

    keys_sorted = sorted(month_groups.keys(), key=lambda ym: (ym[0], ym[1]))
    print(f"Processing {len(keys_sorted)} month groups...")

    def is_leap_year(y: int) -> bool:
        return (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)

    for year, month in keys_sorted:
        if month in (1, 6, 12):
            print(f"  {year}-{month:02d}...")

        for row in month_groups[(year, month)]:
            prod_id = int(row["Product_ID"])
            units_count = int(row["Units_Sold"])

            if prod_id not in product_map or units_count <= 0:
                continue

            pinfo = product_map[prod_id]
            unit_price = pinfo["UnitPrice"]
            sku = pinfo["SKU"]
            tax_rate = categories[pinfo["Category"]]

            remaining = units_count
            while remaining > 0:
                if rng.random() < 0.85:
                    qty = min(rng.randint(1, 5), remaining)
                else:
                    qty = min(rng.randint(6, 12), remaining)

                discount_pct = 0 if rng.random() < 0.60 else rng.randint(5, 30)
                store_id = rng.randint(1, 100)

                gross = round(qty * unit_price, 2)
                discount_amt = round(gross * (discount_pct / 100.0), 2)
                net = round(gross - discount_amt, 2)
                tax_amt = round(net * tax_rate, 2)
                total = round(net + tax_amt, 2)

                if year not in txn_counter_year:
                    txn_counter_year[year] = 0
                txn_counter_year[year] += 1
                txn_id = (
                    f"TXN{year % 100:02d}{store_id:03d}{txn_counter_year[year]:06d}"
                )

                # Max day logic (mirrors PS1 logic: Feb can go up to 29 on leap years, others capped at 28)
                if month == 2:
                    max_day = 29 if is_leap_year(year) else 28
                else:
                    max_day = 28
                day_of_month = rng.randint(1, max_day)
                hour_of_day = rng.randint(8, 21)
                minute = rng.randint(0, 59)
                second = rng.randint(0, 59)

                dt = datetime(year, month, day_of_month, hour_of_day, minute, second)
                date_str = dt.strftime("%Y-%m-%d")
                time_str = dt.strftime("%H:%M:%S")

                region = store_regions[store_id - 1]
                channel = ["InStore", "Online", "Pickup"][rng.randint(0, 2)]
                cust_id = rng.randint(1, 85000)
                cust_type = ["New customer", "Existing regular", "Plus member"][
                    rng.randint(0, 2)
                ]
                payment = ["Credit Card", "Debit Card", "Cash", "Gift Card"][
                    rng.randint(0, 3)
                ]

                # CSV subset for Jan–Feb 2020
                if year == 2020 and month <= 2:
                    csv_line = (
                        f"{line_id},{txn_id},{date_str},{time_str},"
                        f"{store_id},{region},{channel},{cust_id},{cust_type},"
                        f"{prod_id},{sku},{qty},"
                        f"{unit_price:0.2f},{gross:0.2f},{discount_pct},"
                        f"{discount_amt:0.2f},{net:0.2f},{tax_amt:0.2f},{total:0.2f},"
                        f"{payment}"
                    )
                    csv_lines.append(csv_line)

                cur.execute(
                    """
                    INSERT INTO transactions VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        line_id,
                        txn_id,
                        date_str,
                        time_str,
                        store_id,
                        region,
                        channel,
                        cust_id,
                        cust_type,
                        prod_id,
                        sku,
                        qty,
                        unit_price,
                        gross,
                        discount_pct,
                        discount_amt,
                        net,
                        tax_amt,
                        total,
                        payment,
                    ),
                )

                line_id += 1
                processed += 1

                if processed % batch_size == 0:
                    if csv_lines:
                        with open(csv_path, "a", encoding="utf-8") as csv_file:
                            csv_file.write("\n".join(csv_lines) + "\n")
                        csv_lines = []
                    conn.commit()
                    print(f"  Processed {processed} transactions...")

                remaining -= qty

    # Final batch flush
    print("Writing final batch...")
    if csv_lines:
        with open(csv_path, "a", encoding="utf-8") as csv_file:
            csv_file.write("\n".join(csv_lines) + "\n")

    conn.commit()

    print("Exporting SQL dump...")
    with open(sql_path, "w", encoding="utf-8") as sql_file:
        for line in conn.iterdump():
            sql_file.write(f"{line}\n")

    conn.close()

    # Summary
    csv_size_mb = os.path.getsize(csv_path) / (1024 * 1024)
    sql_size_mb = os.path.getsize(sql_path) / (1024 * 1024)
    with open(csv_path, encoding="utf-8") as f:
        csv_row_count = sum(1 for _ in f) - 1  # minus header

    print(f"CSV: {csv_size_mb:0.00} MB, {csv_row_count} rows")
    print(f"SQL: {sql_size_mb:0.00} MB")
    print("Done!")


if __name__ == "__main__":
    main()
