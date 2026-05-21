# CommerceFlow Demo Company Datasets

Enterprise-style sample data for portfolio demos, onboarding, and analysis testing. Each company includes three linked files: **Sales**, **Products**, and **Inventory**.

## Companies

| Company | Sales file | Products file | Inventory file |
|---------|------------|---------------|----------------|
| **Nike** | `sales_nike_q1_2025.xlsx` | `products_nike_catalog.xlsx` | `inventory_nike_warehouse.xlsx` |
| **Apple** | `sales_apple_store_q1_2025.xlsx` | `products_apple_catalog.xlsx` | `inventory_apple_warehouse.xlsx` |
| **Zara** | `sales_zara_global_q1_2025.xlsx` | `products_zara_catalog.xlsx` | `inventory_zara_warehouse.xlsx` |

## What each dataset represents

### Sales (Q1 2025)
- Line-level ecommerce orders with `order_id`, `sku`, `quantity`, `revenue`, `margin`, `sales_channel`, `sold_at`, `region`, `discount_amount`, and `customer`.
- Includes seasonal spikes (launch windows, seasonal peaks), repeat customers, multi-region mix, and profit-leakage discount scenarios.

### Products (catalog)
- Full product master: names, categories, `price`, `cost`, `margin`, `status`, `discount_pct`, `currency`, and `launch_date`.
- Includes clearance/low-margin SKUs and active vs archived lifecycle states.

### Inventory (warehouse)
- Stock positions per SKU: `warehouse`, `on_hand`, `reserved`, `inbound`, `available_units`, aging, turnover, stockout risk, and days remaining.
- Includes dead stock, overstock, and high stockout-risk rows for alert demos.

## How to use in CommerceFlow

1. Open **Data Import** (`/imports`).
2. Upload **one file at a time** (CSV or XLSX). CommerceFlow auto-detects type from column headers.
3. Recommended order for a full demo:
   1. **Products** catalog → detected as **Products**
   2. **Inventory** file → detected as **Inventory**
   3. **Sales** file → detected as **Sales**
4. Go to **Run Analysis** and select the three imports for Products, Sales, and Inventory.
5. Run analysis to populate dashboard, alerts, and recommendations.

### Which file goes where?

| Upload slot in analysis | File pattern |
|-------------------------|--------------|
| **Sales** | `sales_*_q1_2025.xlsx` |
| **Products** | `products_*_catalog.xlsx` |
| **Inventory** | `inventory_*_warehouse.xlsx` |

## Built-in demo labels

After upload, Import History shows friendly names (e.g. **Nike — Q1 2025 Sales**) and company badges when filenames match `nike`, `apple`, or `zara`.

## Regenerating data

```bash
python scripts/generate_demo_datasets.py
```

## Internal QA data

Broken and regression files live in `data/internal_testing/` and are **hidden** from Import History and analysis pickers. Do not use these for customer-facing demos.

## Small starter datasets

Friendly starter files (from `data/sample/`) appear as **Demo Sales Dataset**, **Demo Products Catalog**, and **Demo Inventory Dataset** when uploaded.
