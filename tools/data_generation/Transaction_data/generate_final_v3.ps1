$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$sourcePath = Join-Path $root "Ed_Data\walmart_retail_sales_database.csv"
$sqlPath = Join-Path $root "transaction_database_5yrs_full.sql"
$csvPath = Join-Path $root "transactions_JanFeb_2020.csv"

Write-Host "Loading source data..."
$source = Import-Csv -Path $sourcePath

Write-Host "Building product map..."
$productMap = @{}
$categories = @{}
$rand = [System.Random]::new(42)

foreach ($row in $source) {
    $prodId = [int]$row.Product_ID
    if ($prodId -lt 200 -and -not $productMap.ContainsKey($prodId)) {
        $productMap[$prodId] = @{
            SKU = [string]$row.SKU
            Category = [string]$row.Category
            UnitPrice = [decimal]$row.Unit_Price
        }
        if (-not $categories.ContainsKey($row.Category)) {
            $categories[$row.Category] = [math]::Round(0.02 + ($rand.NextDouble() * 0.03), 4)
        }
    }
}
Write-Host "Loaded $($productMap.Count) products with $($categories.Count) categories"

$storeRegions = @( "Lafayette", "Kokomo", "Naperville", "Indianapolis", "Fort Wayne", "South Bend", "Bloomington", "Terre Haute", "Muncie", "Evansville", "Carmel", "Fishers", "Noblesville", "Greenwood", "Columbus", "West Lafayette", "Gary", "Hammond", "Merrillville", "Valparaiso", "Michigan City", "Crown Point", "Portage", "Hobart", "Schererville", "Dyer", "Munster", "Highland", "Griffith", "La Porte", "Elkhart", "Mishawaka", "Goshen", "Warsaw", "Logansport", "Anderson", "Richmond", "New Castle", "Marion", "Vincennes", "Jasper", "Washington", "Shelbyville", "Franklin", "Lebanon", "Plainfield", "Avon", "Brownsburg", "Zionsville", "Mooresville", "Danville", "Crawfordsville", "Frankfort", "Tipton", "Peru", "Wabash", "Huntington", "Kendallville", "Auburn", "Decatur", "Bluffton", "Angola", "Plymouth", "Nappanee", "Monticello", "Rensselaer", "DeMotte", "Cedar Lake", "Lowell", "Chesterton", "Porter", "Beverly Shores", "Kankakee", "Joliet", "Aurora", "Elgin", "Waukegan", "Evanston", "Oak Park", "Schaumburg", "Arlington Heights", "Skokie", "Des Plaines", "Palatine", "Wheaton", "Downers Grove", "Bolingbrook", "Romeoville", "Peoria", "Springfield", "Champaign", "Normal", "Decatur IL", "Rockford", "Madison", "Milwaukee", "Green Bay", "Appleton", "Oshkosh", "Kenosha", "Racine", "Duluth", "Rochester MN", "St. Cloud", "Sioux Falls", "Fargo", "Bismarck" )

Write-Host "Generating transactions..."

$lineId = 1
$txnCounterYear = @{}
$csvLines = @()
$sqlLines = @()
$batchSize = 1000
$processed = 0

# Write SQL header
"CREATE TABLE `"transactions`" (`"Line_item_ID`" INTEGER, `"Transaction_ID`" TEXT, `"Transaction_Date`" TEXT, `"Transaction_Time`" TEXT, `"Store_ID`" INTEGER, `"Store_Region`" TEXT, `"Order_Channel`" TEXT, `"Customer_ID`" INTEGER, `"Customer_Type`" TEXT, `"Product_ID`" INTEGER, `"SKU`" TEXT, `"Quantity_Sold`" INTEGER, `"Unit_Selling_Price`" REAL, `"Gross_Sales_Value`" REAL, `"Discount_%`" REAL, `"Discount_Amount`" REAL, `"Net_Sales_Value`" REAL, `"Tax_amount`" REAL, `"Total_Value`" REAL, `"Payment_Method`" TEXT);" | Out-File -FilePath $sqlPath -Encoding UTF8

# Write CSV header
"Line_item_ID,Transaction_ID,Transaction_Date,Transaction_Time,Store_ID,Store_Region,Order_Channel,Customer_ID,Customer_Type,Product_ID,SKU,Quantity_Sold,Unit_Selling_Price,Gross_Sales_Value,Discount_%,Discount_Amount,Net_Sales_Value,Tax_amount,Total_Value,Payment_Method" | Out-File -FilePath $csvPath -Encoding UTF8

# Group source data by year and month
$monthGroups = $source | Group-Object Year, Month | Sort-Object @{ Expression = { [int]($_.Name.Split(',')[0]) } }, @{ Expression = { [int]($_.Name.Split(',')[1]) } }

Write-Host "Processing $($monthGroups.Count) month groups..."

foreach ($group in $monthGroups) {
    $nameparts = $group.Name -split ','
    $year = [int]($nameparts[0].Trim())
    $month = [int]($nameparts[1].Trim())
    
    if ($month -in @(1, 6, 12)) { Write-Host "  $year-$($month.ToString('D2'))..." }
    
    foreach ($row in $group.Group) {
        $prodId = [int]$row.Product_ID
        $unitsCount = [int]$row.Units_Sold
        
        if (-not $productMap.ContainsKey($prodId) -or $unitsCount -le 0) { continue }
        
        $pInfo = $productMap[$prodId]
        $unitPrice = $pInfo.UnitPrice
        $sku = $pInfo.SKU
        $taxRate = $categories[$pInfo.Category]
        
        $remaining = $unitsCount
        while ($remaining -gt 0) {
            $qty = if ($rand.NextDouble() -lt 0.85) { 
                [math]::Min($rand.Next(1, 6), $remaining) 
            } else { 
                [math]::Min($rand.Next(6, 13), $remaining) 
            }
            
            $discountPct = if ($rand.NextDouble() -lt 0.60) { 0 } else { $rand.Next(5, 31) }
            $storeId = $rand.Next(1, 101)
            
            $gross = [math]::Round($qty * $unitPrice, 2)
            $discountAmt = [math]::Round($gross * ($discountPct / 100), 2)
            $net = [math]::Round($gross - $discountAmt, 2)
            $taxAmt = [math]::Round($net * $taxRate, 2)
            $total = [math]::Round($net + $taxAmt, 2)
            
            # Transaction ID
            if (-not $txnCounterYear.ContainsKey($year)) { $txnCounterYear[$year] = 0 }
            $txnCounterYear[$year]++
            $txnId = "TXN{0:D2}{1:D3}{2:D6}" -f ($year % 100), $storeId, $txnCounterYear[$year]
            
            # Random date in month
            $maxDay = if ($month -eq 2) { if ([math]::DivRem($year, 4, [ref]$null) -eq 0) { 29 } else { 28 } } else { 28 }
            $dayOfMonth = $rand.Next(1, $maxDay + 1)
            $hourOfDay = $rand.Next(8, 22)
            $minute = $rand.Next(0, 60)
            $second = $rand.Next(0, 60)
            
            $dt = Get-Date -Year $year -Month $month -Day $dayOfMonth -Hour $hourOfDay -Minute $minute -Second $second
            $dateStr = $dt.ToString("yyyy-MM-dd")
            $timeStr = $dt.ToString("HH:mm:ss")
            
            $region = $storeRegions[$storeId - 1]
            $channel = @("InStore", "Online", "Pickup")[$rand.Next(3)]
            $custId = $rand.Next(1, 85001)
            $custType = @("New customer", "Existing regular", "Plus member")[$rand.Next(3)]
            $payment = @("Credit Card", "Debit Card", "Cash", "Gift Card")[$rand.Next(4)]
            
            # Collect CSV line if Jan-Feb 2020
            if ($year -eq 2020 -and $month -le 2) {
                $csvLine = "$lineId,$txnId,$dateStr,$timeStr,$storeId,$region,$channel,$custId,$custType,$prodId,$sku,$qty," + `
                           [string]::Format("{0:0.00}", $unitPrice) + "," + `
                           [string]::Format("{0:0.00}", $gross) + "," + `
                           "$discountPct," + `
                           [string]::Format("{0:0.00}", $discountAmt) + "," + `
                           [string]::Format("{0:0.00}", $net) + "," + `
                           [string]::Format("{0:0.00}", $taxAmt) + "," + `
                           [string]::Format("{0:0.00}", $total) + ",$payment"
                $csvLines += $csvLine
            }
            
            # Collect SQL line
            $sqlLine = "INSERT INTO `"transactions`" VALUES ($lineId,'$txnId','$dateStr','$timeStr',$storeId,'$region','$channel',$custId,'$custType',$prodId,'$sku',$qty," + `
                       [string]::Format("{0:0.00}", $unitPrice) + "," + `
                       [string]::Format("{0:0.00}", $gross) + "," + `
                       "$discountPct," + `
                       [string]::Format("{0:0.00}", $discountAmt) + "," + `
                       [string]::Format("{0:0.00}", $net) + "," + `
                       [string]::Format("{0:0.00}", $taxAmt) + "," + `
                       [string]::Format("{0:0.00}", $total) + ",'$payment');"
            $sqlLines += $sqlLine
            
            $lineId++
            $processed++
            
            # Write in batches
            if ($processed % $batchSize -eq 0) {
                if ($csvLines.Count -gt 0) {
                    $csvLines | Add-Content -Path $csvPath -Encoding UTF8
                    $csvLines = @()
                }
                if ($sqlLines.Count -gt 0) {
                    $sqlLines | Add-Content -Path $sqlPath -Encoding UTF8
                    $sqlLines = @()
                }
                Write-Host "  Processed $processed transactions..."
            }
            
            $remaining -= $qty
        }
    }
}

# Final batch
Write-Host "Writing final batch..."
if ($csvLines.Count -gt 0) {
    $csvLines | Add-Content -Path $csvPath -Encoding UTF8
}
if ($sqlLines.Count -gt 0) {
    $sqlLines | Add-Content -Path $sqlPath -Encoding UTF8
}

$csvSize = (Get-Item $csvPath).Length / 1MB
$sqlSize = (Get-Item $sqlPath).Length / 1MB
$csvrowCount = (Get-Content $csvPath | Measure-Object -Line).Lines

Write-Host "CSV: $($csvSize.ToString('0.00')) MB,"($csvrowCount - 1) "rows"
Write-Host "SQL: $($sqlSize.ToString('0.00')) MB"
Write-Host "Done!"
