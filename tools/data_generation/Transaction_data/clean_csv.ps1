# Clean CSV file by removing [string] prefixes
$file = 'e:\Purdue MBT\Academics\Spring_2026_classes\59000_Emerging_Tech_and Business\AI_Tech_Project\Synthetic_Retail_data\transaction_database_2020_JanFeb.csv'
$content = [System.IO.File]::ReadAllText($file)
$cleaned = $content -replace '\[string\]', ''
[System.IO.File]::WriteAllText($file, $cleaned, [System.Text.Encoding]::UTF8)
Write-Host "Successfully cleaned! All [string] prefixes removed from $file"
