# Walmart-Style Retail Sales Database
## Complete Package - Quick Start Guide

---

## 📦 What's Included

### Main Database
- **walmart_retail_sales_database.csv** (1.36 MB)
  - 12,000 sales records
  - 200 unique products
  - 60 months of data (Jan 2020 - Dec 2024)
  - $13+ million in total revenue

### Supporting Files
- **PRODUCT_CATALOG.csv** - 200 unique products with details
- **SAMPLE_DATA.csv** - 72-record sample showing variety
- **monthly_sales_summary.csv** - Monthly aggregated sales
- **category_yearly_performance.csv** - Category trends by year
- **brand_performance.csv** - Brand-level analytics
- **pack_quantity_analysis.csv** - Analysis by pack size and category
- **DATA_DICTIONARY.md** - Complete documentation

---

## 🚀 Quick Start

### Database Structure

**Each record contains:**
```
Product_ID, SKU, Category, Brand, Sub_Brand, Product_Name, 
Presentation, Pack_Quantity, Product_Description, Ingredients_List,
Unit_Price, Year, Month, Units_Sold, Total_Sales_Value
```

### Example Record
```csv
1,DETARI0001,Detergents and Cleaning,Ariel,Ariel Regular,
Ariel Regular 32 oz,32 oz,1,"Advanced stain-fighting technology",
"Water, Sodium Laureth Sulfate...",5.68,2020,1,193,1096.24
```

### Example Multi-Pack Record
```csv
10,DETDOW0010,Detergents and Cleaning,Downy,Downy April Fresh,
Downy April Fresh 48 pods,48 pods,48,"Concentrated formula provides excellent cleaning",
"Polyvinyl Alcohol Film, Water, Sodium Carbonate...",14.37,2020,1,203,2917.11
```

---

## 📊 Database at a Glance

### Products by Category
```
Dry and Canned Foods ......... 50 products (25%)
Detergents and Cleaning ...... 40 products (20%)
Beverages .................... 40 products (20%)
Dairy and Refrigerated ....... 30 products (15%)
Snacks and Candy ............. 20 products (10%)
Personal Care ................ 10 products (10%)
```

### Revenue by Category (5 years)
```
Beverages ................. $3,509,010.90 (27%)
Detergents & Cleaning ..... $3,387,141.66 (26%)
Dry & Canned Foods ........ $2,501,615.47 (19%)
Snacks & Candy ............ $1,541,272.45 (12%)
Dairy & Refrigerated ...... $1,341,565.82 (10%)
Personal Care ............. $  763,188.56 (6%)
```

### Top 5 Products by Revenue
```
1. Downy April Fresh 48 pods ............ $230,238.57
2. Gatorade Lemon-Lime 24-pack .......... $218,213.25
3. Nestlé Pure Life Water 24-pack ....... $215,723.80
4. Hershey's Kisses 13 oz ............... $208,880.16
5. Monster Energy Ultra 12-pack ......... $203,656.44
```

---

## 🔍 Sample Queries

### Python/Pandas
```python
import pandas as pd

# Load the database
df = pd.read_csv('walmart_retail_sales_database.csv')

# Total revenue by year
yearly_revenue = df.groupby('Year')['Total_Sales_Value'].sum()
print(yearly_revenue)

# Top 10 products
top_products = df.groupby('Product_Name')['Total_Sales_Value'].sum()
print(top_products.nlargest(10))

# Category performance
category_stats = df.groupby('Category').agg({
    'Total_Sales_Value': 'sum',
    'Units_Sold': 'sum',
    'Unit_Price': 'mean'
})
print(category_stats)
```

### SQL
```sql
-- Load into your database, then:

-- Monthly sales trend
SELECT Year, Month, 
       SUM(Total_Sales_Value) as Revenue,
       SUM(Units_Sold) as Units
FROM walmart_retail_sales_database
GROUP BY Year, Month
ORDER BY Year, Month;

-- Brand comparison
SELECT Brand, Category,
       COUNT(DISTINCT SKU) as Products,
       SUM(Total_Sales_Value) as Total_Revenue,
       AVG(Units_Sold) as Avg_Units_Per_Month
FROM walmart_retail_sales_database
GROUP BY Brand, Category
ORDER BY Total_Revenue DESC;

-- Seasonal analysis for beverages
SELECT Month,
       AVG(Units_Sold) as Avg_Units,
       AVG(Total_Sales_Value) as Avg_Revenue
FROM walmart_retail_sales_database
WHERE Category = 'Beverages'
GROUP BY Month
ORDER BY Month;
```

### Excel
```
1. Open walmart_retail_sales_database.csv in Excel
2. Create PivotTable (Insert > PivotTable)
3. Add fields:
   - Rows: Category, Brand
   - Values: Sum of Total_Sales_Value
   - Filters: Year, Month
4. Create charts to visualize trends
```

---

## 📈 Key Features

### ✓ Realistic Seasonality
- Beverages peak in summer (+30-60%)
- Cleaning products spike in January (+40-70%)
- Snacks increase during holidays (+30-60%)
- All categories show natural monthly variation

### ✓ Multi-Year Trends
- COVID impact on cleaning products (2020-2021 boost)
- Health-conscious beverage decline (-2% yearly)
- Growing categories: Snacks (+4%), Personal Care (+3%)
- Stable categories: Dry Foods (+1%)

### ✓ Price Realism
- Larger presentations = higher prices
- Price range: $0.91 - $19.65
- Average transaction: $1,086.98
- Consistent brand pricing within category

### ✓ Volume Patterns
- High-volume: Beverages (avg 504 units/month)
- Low-volume: Detergents (avg 137 units/month)
- Some zero-sales months (5% realistic stock-outs)
- Range: 0 - 1,615 units per product per month

### ✓ Pack Quantity Mix
- 160 single-unit products (69% of revenue)
- 40 multi-pack products (31% of revenue)
- Pack sizes: 1, 2, 3, 4, 6, 12, 24, 48, 72 units
- Multi-packs include: beverage cases, detergent pods, snack packs
- Higher pack quantities = higher prices (e.g., 48-pack avg $15.28 vs 1-pack avg $3.98)

### ✓ Product Information
- **Descriptions:** Marketing-style product descriptions (60-100 characters)
- **Ingredients:** Complete, realistic ingredient lists following FDA standards
- **Detail Level:** Varies by category (simple to complex formulations)
- **Use Cases:** NLP analysis, allergen identification, health trends, text mining

---

## 💡 Use Cases

### Business Analytics
- Sales forecasting models
- Seasonal demand planning
- Inventory optimization
- Price elasticity analysis
- Category management strategies

### Data Science
- Time series forecasting
- Machine learning models
- Clustering analysis
- Predictive analytics
- A/B testing frameworks

### Education & Training
- SQL practice exercises
- Business intelligence dashboards
- Data visualization projects
- Retail management case studies
- Statistical analysis tutorials

### Portfolio Projects
- Interactive dashboards (Tableau, Power BI)
- Python data analysis notebooks
- Automated reporting systems
- Database design examples
- API development practice

---

## 📋 Data Quality Checklist

✅ No missing values (100% complete)  
✅ Unique Product_IDs and SKUs  
✅ Consistent pricing across time  
✅ Realistic sales patterns  
✅ Proper date ranges (60 months)  
✅ Accurate calculations (Units × Price = Total)  
✅ Representative brand mix  
✅ Logical category distribution  

---

## 🎯 Common Analysis Questions

**This database can answer:**

1. Which products generate the most revenue?
2. How do sales vary by season?
3. Which categories are growing/declining?
4. What's the average price by category?
5. How did COVID affect different categories?
6. Which brands perform best?
7. What are the sales patterns by month?
8. Which products have the highest volume?
9. How stable are sales year-over-year?
10. What's the revenue distribution across categories?

---

## 📚 Additional Resources

- **DATA_DICTIONARY.md** - Full documentation with column definitions
- **PRODUCT_CATALOG.csv** - Browse all 200 products with pack quantities
- **monthly_sales_summary.csv** - Pre-aggregated monthly totals
- **category_yearly_performance.csv** - Category trends
- **brand_performance.csv** - Brand-level statistics
- **pack_quantity_analysis.csv** - Pack size performance analysis

---

## 🔄 Data Versioning

**Version:** 2.0  
**Created:** January 2026  
**Coverage:** January 2020 - December 2024  
**Records:** 12,000  
**Products:** 200  
**Categories:** 6  
**Brands:** 75  
**Columns:** 15
**File Size:** 3.80 MB

**Version 2.0 Features:**
- ✓ Pack Quantity field
- ✓ Product Descriptions
- ✓ Complete Ingredients Lists

---

## ⚠️ Important Notes

1. **Synthetic Data**: This is simulated data for analytical purposes
2. **Privacy**: No real customer or transaction data included
3. **Trends**: Based on realistic retail patterns but simplified
4. **Purpose**: Educational, analytical, and demonstration use
5. **Accuracy**: Patterns are illustrative, not predictive

---

## 🚀 Getting Started Checklist

- [ ] Download all CSV files
- [ ] Review DATA_DICTIONARY.md for column definitions
- [ ] Examine SAMPLE_DATA.csv to understand structure
- [ ] Import walmart_retail_sales_database.csv into your tool
- [ ] Run sample queries to verify data
- [ ] Explore seasonal patterns in beverages/cleaning
- [ ] Create your first visualization
- [ ] Build your analysis or model

---

## 💪 Challenge Ideas

### Beginner
1. Calculate total revenue by category
2. Find the best-selling product
3. Identify which month has highest sales
4. Compare 2020 vs 2024 performance

### Intermediate
5. Create monthly sales trend visualizations
6. Analyze seasonal patterns by category
7. Build a category performance dashboard
8. Calculate year-over-year growth rates

### Advanced
9. Develop a demand forecasting model
10. Create a recommendation system
11. Perform time series decomposition
12. Build an automated reporting pipeline
13. Analyze ingredient trends (organic, natural, artificial)
14. Perform text analysis on product descriptions
15. Create allergen identification system
16. Build NLP model for product categorization

---

## 📧 Questions?

This dataset was created with careful attention to realistic retail patterns. For detailed documentation, see DATA_DICTIONARY.md.

**Happy Analyzing! 📊**
