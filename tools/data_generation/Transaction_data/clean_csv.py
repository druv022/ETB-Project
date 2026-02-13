#!/usr/bin/env python3
import sys

file_path = r'e:\Purdue MBT\Academics\Spring_2026_classes\59000_Emerging_Tech_and Business\AI_Tech_Project\Synthetic_Retail_data\transaction_database_2020_JanFeb.csv'

# Read the file
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove all [string] prefixes
cleaned_content = content.replace('[string]', '')

# Write back to the file
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(cleaned_content)

print('File cleaned successfully! All [string] prefixes removed.')
sys.exit(0)
