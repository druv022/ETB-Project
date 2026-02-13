# Walmart-Style Retail Sales Database
## Data Dictionary & Documentation

---

## Overview

This database contains **12,000 sales records** for **200 products** across **60 months** (January 2020 - December 2024), simulating realistic retail sales data for a Walmart-style store.

**Total Revenue (5 years):** $13,043,794.86  
**Average Monthly Revenue:** $217,396.58

---

## File Structure

### Main Files

1. **walmart_retail_sales_database.csv** (12,000 records)
   - Complete sales database with all transactions
   - One record per product per month

2. **monthly_sales_summary.csv** (60 records)
   - Aggregated monthly sales totals
   - Year, Month, Units Sold, Revenue

3. **category_yearly_performance.csv** (360 records)
   - Sales by category and year
   - Category, Year, Total Sales Value, Units Sold

4. **brand_performance.csv** (75 records)
   - Aggregated performance by brand
   - Brand, Total Revenue, Total Units, Number of SKUs

---

## Column Definitions

### walmart_retail_sales_database.csv

| Column Name | Data Type | Description | Example |
|------------|-----------|-------------|---------|
| **Product_ID** | Integer | Unique identifier for each product (1-200) | 1 |
| **SKU** | String | Stock Keeping Unit - unique alphanumeric code | DETARI0001 |
| **Category** | String | Main product category | Detergents and Cleaning |
| **Brand** | String | Brand name (e.g., Coca-Cola, Tide, Dove) | Tide |
| **Sub_Brand** | String | Specific product line or variant | Tide Original |
| **Product_Name** | String | Full descriptive name with presentation | Tide Original 2L |
| **Presentation** | String | Package size or format | 2L, 500ml, 12 oz, 6-pack |
| **Pack_Quantity** | Integer | Number of units per package (1 for singles, 6 for 6-packs, etc.) | 1, 6, 12, 24, 48 |
| **Product_Description** | String | Marketing description of product features and benefits | "Advanced stain-fighting technology with a long-lasting fresh scent" |
| **Ingredients_List** | String | Complete list of ingredients in order of quantity | "Water, Sodium Laureth Sulfate, Linear Alkylbenzene Sulfonate..." |
| **Unit_Price** | Decimal | Price per unit in USD (2 decimals) | 5.68 |
| **Year** | Integer | Year of sale (2020-2024) | 2020 |
| **Month** | Integer | Month of sale (1-12) | 1 |
| **Units_Sold** | Integer | Number of units sold in that month | 193 |
| **Total_Sales_Value** | Decimal | Revenue (Units_Sold × Unit_Price) | 1096.24 |

---

## Product Categories

### Distribution

| Category | Product Count | % of Total | Revenue (5 years) |
|----------|--------------|------------|-------------------|
| **Dry and Canned Foods** | 50 | 25% | $2,501,615.47 |
| **Detergents and Cleaning** | 40 | 20% | $3,387,141.66 |
| **Beverages** | 40 | 20% | $3,509,010.90 |
| **Dairy and Refrigerated** | 30 | 15% | $1,341,565.82 |
| **Snacks and Candy** | 20 | 10% | $1,541,272.45 |
| **Personal Care** | 20 | 10% | $763,188.56 |

---

## Brand Examples by Category

### Detergents and Cleaning
- Tide (Original, Plus Bleach, Free & Gentle, Pods)
- Ariel (Regular, Color, Mountain Spring)
- Ajax (Lemon, Lavender, Antibacterial)
- Fabuloso (Lavender, Lemon, Ocean)
- Clorox (Regular, Splash-Less, Disinfecting)
- Mr. Clean, Downy, Pine-Sol

### Beverages
- Coca-Cola (Regular, Zero, Diet, Cherry)
- Pepsi (Regular, Zero Sugar, Diet)
- Sprite, Fanta (Orange, Grape, Strawberry)
- Gatorade (Lemon-Lime, Fruit Punch, Orange)
- Nestlé Pure Life Water
- Red Bull, Monster Energy
- Arizona Tea

### Dry and Canned Foods
- Campbell's Soups
- Del Monte (Corn, Green Beans, Peaches, Pineapple)
- Goya Beans
- Barilla Pasta
- Quaker Oats
- Kellogg's Cereals
- General Mills (Cheerios, Lucky Charms)

### Dairy and Refrigerated
- Dannon, Yoplait, Chobani Yogurts
- Kraft Cheese
- Philadelphia Cream Cheese
- Great Value Milk and Butter
- Land O'Lakes
- Tropicana Orange Juice

### Snacks and Candy
- Lay's, Doritos, Cheetos
- Hershey's, M&M's, Snickers, Kit Kat
- Oreo (Original, Double Stuf, Golden)

### Personal Care
- Dove, Colgate, Crest
- Head & Shoulders, Pantene
- Gillette, Degree, Secret

---

## Realistic Features

### 1. Seasonal Variations

**Beverages**
- Peak: Summer months (May-September): +30-60% sales
- Low: Winter months (November-February): -10-30% sales

**Detergents and Cleaning**
- Peak: January (New Year cleaning): +40-70% sales
- Peak: Spring (April-May): +20-40% sales

**Snacks and Candy**
- Peak: October-December (holidays): +30-60% sales
- Moderate increase: February (Valentine's), July (July 4th)

**Dairy and Refrigerated**
- Slight increase in summer: +10-30% sales

**Personal Care**
- Increase before summer and holidays: +10-30% sales

**Dry and Canned Foods**
- Relatively stable, slight increase fall/winter: +5-20% sales

### 2. Long-term Trends (2020-2024)

**Growth Categories:**
- Personal Care: +3% annually
- Snacks and Candy: +4% annually
- Dairy and Refrigerated: +2% annually

**Stable/Declining:**
- Beverages: -2% annually (health consciousness)
- Dry and Canned Foods: +1% annually (very stable)

**COVID Impact:**
- Detergents and Cleaning: +15% in 2020-2021, then gradual decline

### 3. Price Ranges

| Category | Min Price | Max Price | Average Price |
|----------|-----------|-----------|---------------|
| Beverages | $1.17 | $19.65 | $6.23 |
| Dairy | $0.91 | $4.57 | $2.58 |
| Detergents | $4.20 | $17.58 | $10.89 |
| Dry Foods | $1.19 | $5.47 | $2.78 |
| Personal Care | $1.41 | $6.38 | $3.92 |
| Snacks | $0.91 | $6.22 | $3.15 |

### 4. Sales Volume Characteristics

- **Zero Sales:** ~5% of all records (realistic out-of-stock or no demand)
- **Volume Range:** 0 - 1,615 units per product per month
- **Average Monthly Units:** 318 units per product
- **High-volume products:** Beverages (avg 504 units/month)
- **Low-volume products:** Detergents (avg 137 units/month)

### 5. Pack Quantity Distribution

The database includes both single-unit and multi-pack products:

| Pack Quantity | Products | % of Revenue | Example Products |
|---------------|----------|--------------|------------------|
| **1-pack** (Singles) | 160 | 69.1% | Individual bottles, single cans, single packages |
| **6-pack** | 10 | 8.7% | Soda 6-packs, yogurt 6-packs, beverage multipacks |
| **48-pack** (Pods) | 8 | 7.4% | Detergent pods, cleaning pods |
| **24-pack** | 7 | 5.0% | Beverage cases, large multipacks |
| **12-pack** | 4 | 4.5% | Soda 12-packs, snack multipacks |
| **4-pack** | 7 | 3.1% | Yogurt 4-packs, small multipacks |
| **72-pack** (Pods) | 1 | 1.2% | Large detergent pod packages |
| **3-pack** | 2 | 0.7% | Personal care 3-packs |
| **2-pack** | 1 | 0.3% | Personal care 2-packs |

**Pack Quantity Pricing:**
- Average 1-pack price: $3.98
- Average 6-pack price: $6.11
- Average 12-pack price: $10.21
- Average 48-pack price: $15.28

**Top Multi-Pack Products:**
1. Gatorade Lemon-Lime 24-pack: $231,535.95
2. Downy April Fresh 48 pods: $230,238.57
3. Pepsi Zero Sugar 12-pack: $165,166.00

### 6. Product Descriptions and Ingredients

**Product Descriptions:**
Each product includes a marketing-style description highlighting key features and benefits:
- Detergents: Emphasize cleaning power, scent, stain-fighting technology
- Beverages: Focus on refreshment, taste, energy benefits
- Food: Highlight quality, flavor, convenience
- Personal Care: Stress effectiveness, gentleness, protection
- Average length: 60-100 characters

**Examples:**
- "Advanced stain-fighting technology with a long-lasting fresh scent"
- "Refreshing taste that quenches your thirst"
- "Premium quality ingredients for delicious home-cooked meals"
- "Gentle formula for daily care and protection"

**Ingredients Lists:**
Complete, realistic ingredient lists following FDA labeling requirements:
- Listed in descending order by quantity
- Includes chemical names for cleaning products
- Food ingredients include enrichment vitamins/minerals
- Personal care products list active and inactive ingredients
- Realistic complexity (simple products: 5-10 ingredients, complex: 20+ ingredients)

**Ingredient Variety by Category:**
- **Beverages:** Water, sweeteners, acids, flavors, preservatives, vitamins
- **Food:** Main ingredient, enrichment (vitamins/minerals), preservatives
- **Detergents:** Surfactants, enzymes, fragrances, preservatives, pH adjusters
- **Personal Care:** Active ingredients, emulsifiers, fragrances, preservatives

---

## Top Performing Products

### By Revenue (5 years)

1. **Downy April Fresh 48 pods** - $230,238.57
2. **Gatorade Lemon-Lime 24-pack** - $218,213.25
3. **Nestlé Pure Life Water 24-pack** - $215,723.80
4. **Hershey's Kisses 13 oz** - $208,880.16
5. **Monster Energy Ultra 12-pack** - $203,656.44

### Top Brands by Revenue

1. **Fanta** - $791,462.54 (10 SKUs)
2. **Ajax** - $757,219.10 (9 SKUs)
3. **Downy** - $588,114.20 (6 SKUs)
4. **Monster** - $562,310.49 (6 SKUs)
5. **Mr. Clean** - $532,916.97 (7 SKUs)

---

## Use Cases

This database is ideal for:

1. **Sales Analysis & Forecasting**
   - Time series analysis
   - Seasonal decomposition
   - Trend identification

2. **Business Intelligence**
   - Category performance analysis
   - Brand comparison
   - Price elasticity studies

3. **Machine Learning**
   - Demand forecasting models
   - Inventory optimization
   - Customer segmentation (with additional customer data)

4. **Data Visualization**
   - Dashboard creation
   - Sales trend charts
   - Category heatmaps

5. **Academic/Training**
   - SQL practice queries
   - Business analytics exercises
   - Retail management case studies

6. **Product Analysis**
   - Ingredient analysis and trends
   - Product description NLP projects
   - Health/nutrition studies
   - Allergen identification
   - Natural language processing on descriptions

7. **Marketing & Consumer Insights**
   - Description effectiveness analysis
   - Product feature correlations with sales
   - Text mining on product descriptions

---

## Data Quality Notes

✓ **Complete data:** No missing values  
✓ **Realistic patterns:** Includes seasonality and trends  
✓ **Price consistency:** Larger presentations = higher prices  
✓ **Brand diversity:** 75 unique brands across 200 products  
✓ **Time coverage:** Full 5 years of monthly data  
✓ **Realistic zeros:** Some months show zero sales (5% of records)

---

## Sample Queries

### SQL Examples

```sql
-- Total revenue by year
SELECT Year, SUM(Total_Sales_Value) as Total_Revenue
FROM walmart_retail_sales_database
GROUP BY Year
ORDER BY Year;

-- Top 10 products by revenue
SELECT Product_Name, Brand, SUM(Total_Sales_Value) as Revenue
FROM walmart_retail_sales_database
GROUP BY Product_Name, Brand
ORDER BY Revenue DESC
LIMIT 10;

-- Monthly sales trend for beverages
SELECT Year, Month, SUM(Units_Sold) as Units, SUM(Total_Sales_Value) as Revenue
FROM walmart_retail_sales_database
WHERE Category = 'Beverages'
GROUP BY Year, Month
ORDER BY Year, Month;

-- Category performance comparison
SELECT Category, 
       SUM(Total_Sales_Value) as Total_Revenue,
       SUM(Units_Sold) as Total_Units,
       AVG(Unit_Price) as Avg_Price
FROM walmart_retail_sales_database
GROUP BY Category
ORDER BY Total_Revenue DESC;
```

---

## Version Information

**Database Version:** 2.0  
**Creation Date:** January 2026  
**Data Period:** January 2020 - December 2024  
**Total Records:** 12,000  
**Total Products:** 200  
**Total Columns:** 15
**File Size:** 3.80 MB

**Version 2.0 Updates:**
- Added Pack_Quantity field
- Added Product_Description field
- Added Ingredients_List field  

---

## Contact & Feedback

This synthetic dataset was created for analytical and educational purposes. The data patterns are based on realistic retail trends but do not represent actual Walmart or any other retailer's data.
