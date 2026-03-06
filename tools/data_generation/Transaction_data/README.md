# Transaction Data Generation

This directory contains scripts to generate synthetic retail transaction data for the ETB Project.

## 🔄 Generating Transaction Data

The large SQL transaction database file is **not included in the repository** because it exceeds GitHub's 100MB limit (176+ MB). You need to generate it locally using the provided script.

The CSV sample file (`transactions_JanFeb_2020.csv`) **is included** in the repository for convenience.

### Prerequisites

- PowerShell (Windows) or PowerShell Core (cross-platform)
- Source data file: `Ed_Data/walmart_retail_sales_database.csv` (included in repository)

### How to Generate

Run the main generation script:

```powershell
.\generate_final_v3.ps1
```

This script will:
1. Read the source data from `Ed_Data/walmart_retail_sales_database.csv`
2. Generate **transaction_database_5yrs_full.sql** (~176 MB) - **not included in repo**
   - Contains SQL INSERT statements for all transactions from 2020-2024
   - Includes 5 years of synthetic transaction data
   - Too large for GitHub (exceeds 100 MB limit)
3. Generate **transactions_JanFeb_2020.csv** (~3.6 MB) - **included in repo**
   - CSV extract of January-February 2020 transactions
   - Useful for testing and analysis
   - Available in the repository for quick access

### Generated Files

| File | Size | Included in Repo | Description |
|------|------|------------------|-------------|
| `transaction_database_5yrs_full.sql` | ~176 MB | ❌ No | Complete 5-year transaction database (SQL format) - must be generated locally |
| `transactions_JanFeb_2020.csv` | ~3.6 MB | ✅ Yes | CSV extract for Jan-Feb 2020 - included for quick access |

**Note**: Only the large SQL file is excluded from the repository. The CSV sample file is included for convenience.

## 📊 What Data is Generated?

The script creates realistic retail transactions with:
- **100 stores** across multiple regions
- **200 products** from the source catalog
- **5 years** of transaction history (2020-2024)
- Multiple transaction attributes:
  - Transaction ID, Date, Time
  - Store ID and Region
  - Order Channel (InStore/Online/Pickup)
  - Customer ID and Type
  - Product details (ID, SKU, Quantity)
  - Pricing (Unit Price, Gross, Discounts, Net, Tax, Total)
  - Payment Method

## 🛠️ Other Scripts

- **clean_csv.ps1** / **clean_csv.py**: Utilities for CSV data cleaning
- **generate_reconciliation.ps1**: Generates reconciliation summaries

## ⚠️ Important Notes

1. **Large Files**: The generated SQL file is too large for GitHub (>100 MB limit)
2. **CSV Included**: The `transactions_JanFeb_2020.csv` file is included in the repository
3. **Local Generation**: Generate the full SQL database locally when needed
4. **Seed Value**: The script uses a fixed random seed (42) for reproducible results
5. **Processing Time**: Generation may take several minutes depending on your system

## 📝 Data Source

The generation script uses the Walmart-style retail sales database located in:
```
Ed_Data/walmart_retail_sales_database.csv
```

See `Ed_Data/README.md` for complete details about the source data.

## 🚀 Quick Start

```powershell
# Navigate to this directory
cd tools/data_generation/Transaction_data

# Run the generator
.\generate_final_v3.ps1

# Check the output
# - transaction_database_5yrs_full.sql should be ~176 MB
# - transactions_JanFeb_2020.csv should be generated
```

## 📧 Questions?

For issues with data generation, check:
- The source CSV file exists and is readable
- You have sufficient disk space (~200 MB free)
- PowerShell execution policy allows script execution
