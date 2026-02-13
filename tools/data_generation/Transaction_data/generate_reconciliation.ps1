$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$sourcePath = Join-Path $root "Ed_Data\walmart_retail_sales_database.csv"
$sqlPath = Join-Path $root "transactions_database.sql"
$reconPath = Join-Path $root "reconciliation_report.csv"
$reconSummaryPath = Join-Path $root "reconciliation_summary.txt"

$inv = [System.Globalization.CultureInfo]::InvariantCulture

function Format-Decimal([decimal]$value) {
    return [string]::Format($inv, "{0:0.00}", $value)
}

Write-Host "Loading source data..."
$source = Import-Csv $sourcePath

$recon = @{}
foreach ($row in $source) {
    $productId = [int]$row.Product_ID
    $year = [int]$row.Year
    $month = [int]$row.Month
    $key = "$productId|$year|$month"

    if (-not $recon.ContainsKey($key)) {
        $recon[$key] = [pscustomobject]@{
            Product_ID = $productId
            Year = $year
            Month = $month
            MonthlyUnits = [int]$row.Units_Sold
            MonthlySales = [decimal]$row.Total_Sales_Value
            TxnUnits = 0
            TxnSales = 0.0
        }
    }
}

Write-Host "Parsing SQL inserts..."
$reader = [System.IO.StreamReader]::new($sqlPath)
try {
    while (-not $reader.EndOfStream) {
        $line = $reader.ReadLine()
        if (-not $line.StartsWith("INSERT INTO")) { continue }

        $valuesIndex = $line.IndexOf("VALUES (")
        if ($valuesIndex -lt 0) { continue }

        $valuesPart = $line.Substring($valuesIndex + 8)
        $valuesPart = $valuesPart.TrimEnd(");")
        $parts = $valuesPart -split ","
        if ($parts.Count -lt 20) { continue }

        $dateText = $parts[2].Trim("'")
        $year = [int]$dateText.Substring(0, 4)
        $month = [int]$dateText.Substring(5, 2)
        $productId = [int]$parts[9]
        $qty = [int]$parts[11]
        $net = [decimal]$parts[16]

        $key = "$productId|$year|$month"
        if (-not $recon.ContainsKey($key)) {
            $recon[$key] = [pscustomobject]@{
                Product_ID = $productId
                Year = $year
                Month = $month
                MonthlyUnits = 0
                MonthlySales = 0.0
                TxnUnits = 0
                TxnSales = 0.0
            }
        }

        $recon[$key].TxnUnits += $qty
        $recon[$key].TxnSales += $net
    }
}
finally {
    $reader.Close()
}

Write-Host "Writing reconciliation report..."
$reconWriter = New-Object System.IO.StreamWriter($reconPath, $false, [System.Text.Encoding]::UTF8)
$reconWriter.WriteLine("Product_ID,Year,Month,MonthlyUnits,TxnUnitsSum,UnitsMatch,MonthlySales,TxnNetSalesSum,SalesDiff,SalesDiffPct")

$unitMismatchCount = 0
$salesDiffs = New-Object System.Collections.Generic.List[decimal]

$reconValues = $recon.Values | Sort-Object Year, Month, Product_ID
foreach ($r in $reconValues) {
    $unitsMatch = ($r.MonthlyUnits -eq $r.TxnUnits)
    if (-not $unitsMatch) { $unitMismatchCount++ }

    $salesDiff = [decimal]$r.TxnSales - [decimal]$r.MonthlySales
    if ($r.MonthlySales -ne 0) {
        $salesDiffPct = [math]::Round(([double]$salesDiff / [double]$r.MonthlySales) * 100, 4)
    } else {
        $salesDiffPct = 0
    }

    $salesDiffs.Add([decimal]$salesDiff)

    $line = @(
        $r.Product_ID,
        $r.Year,
        $r.Month,
        $r.MonthlyUnits,
        $r.TxnUnits,
        $unitsMatch,
        (Format-Decimal $r.MonthlySales),
        (Format-Decimal $r.TxnSales),
        (Format-Decimal $salesDiff),
        $salesDiffPct
    ) -join ","

    $reconWriter.WriteLine($line)
}

$reconWriter.Close()

$absDiffs = $salesDiffs | ForEach-Object { [math]::Abs([double]$_) }
$maxDiff = if ($absDiffs.Count -gt 0) { ($absDiffs | Measure-Object -Maximum).Maximum } else { 0 }
$meanDiff = if ($absDiffs.Count -gt 0) { ($absDiffs | Measure-Object -Average).Average } else { 0 }

$summaryLines = @(
    "Unit mismatches: $unitMismatchCount",
    ("Max absolute sales diff: {0:0.00}" -f $maxDiff),
    ("Mean absolute sales diff: {0:0.00}" -f $meanDiff)
)

[System.IO.File]::WriteAllLines($reconSummaryPath, $summaryLines)

Write-Host "Done."
Write-Host "Recon report: $reconPath"
Write-Host "Recon summary: $reconSummaryPath"
