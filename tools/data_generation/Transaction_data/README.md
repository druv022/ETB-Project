# Transaction Data Generation

This directory contains scripts to generate synthetic retail transaction data for the ETB Project.

## 🔄 Generating Transaction Data

The transaction database files are **not included in the repository** because they are very large (176+ MB). You need to generate them locally using the provided scripts.

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
2. Generate **transaction_database_5yrs_full.sql** (~176 MB)
   - Contains SQL INSERT statements for all transactions from 2020-2024
   - Includes 5 years of synthetic transaction data
3. Generate **transactions_JanFeb_2020.csv**
   - CSV extract of January-February 2020 transactions
   - Useful for testing and analysis

### Generated Files

| File | Size | Description |
|------|------|-------------|
| `transaction_database_5yrs_full.sql` | ~176 MB | Complete 5-year transaction database (SQL format) |
| `transactions_JanFeb_2020.csv` | Variable | CSV extract for Jan-Feb 2020 |

**Note**: These files are listed in `.gitignore` and should **not** be committed to the repository.

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
2. **Local Generation**: Always generate these files locally when needed
3. **Seed Value**: The script uses a fixed random seed (42) for reproducible results
4. **Processing Time**: Generation may take several minutes depending on your system

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
