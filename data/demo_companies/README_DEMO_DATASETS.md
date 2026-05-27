# CommerceFlow Demo Company Datasets

Enterprise-style sample data for portfolio demos, onboarding, and analysis testing. The public guest workspace uses **Atlas Retail Group** only — three linked files: **Sales**, **Products**, and **Inventory**.

## Atlas Retail Group (public demo)

| Dataset | File |
|---------|------|
| **Sales** | `atlas_sales_q1_2026.xlsx` |
| **Products** | `atlas_products.xlsx` |
| **Inventory** | `atlas_inventory.xlsx` |

## What each dataset represents

### Sales (Q1 2026)
- Line-level ecommerce orders with `order_id`, `sku`, `quantity`, `revenue`, `margin`, `sales_channel`, `sold_at`, `region`, `discount_amount`, and `customer`.
- Includes seasonal spikes, repeat customers, multi-region mix, and profit-leakage discount scenarios.

### Products (catalog)
- Full product master: names, categories, `price`, `cost`, `margin`, `status`, `discount_pct`, `currency`, and `launch_date`.
- Includes clearance/low-margin SKUs and active vs archived lifecycle states.

### Inventory (warehouse)
- Stock positions per SKU: `warehouse`, `on_hand`, `reserved`, `inbound`, `available_units`, aging, turnover, stockout risk, and days remaining.
- Includes dead stock, overstock, slow movers, and high stockout-risk rows for alert demos.

## How to use in CommerceFlow

1. Open **Data Import** (`/imports`) or launch **Explore Sample Workspace** from the landing page (`/dashboard?demo=atlas`).
2. Upload **one file at a time** (CSV or XLSX). CommerceFlow auto-detects type from column headers.
3. Recommended order for a full demo:
   1. **Products** → `atlas_products.xlsx`
   2. **Inventory** → `atlas_inventory.xlsx`
   3. **Sales** → `atlas_sales_q1_2026.xlsx`
4. Go to **Run Analysis** and select the three Atlas imports.
5. Run analysis to populate dashboard, alerts, and recommendations.

## Built-in demo labels

After upload, Import History shows friendly names (e.g. **Atlas Retail Group — Retail Sales Dataset**) when filenames match `atlas_*`.

## Regenerating data

```bash
python scripts/generate_atlas_demo.py
python scripts/sync_atlas_demo_environment.py
```

`generate_atlas_demo.py` rebuilds the XLSX packs, runs production analytics for preview numbers, and syncs `landing/src/config.ts`.

## Internal QA data

Broken and regression files live in `data/internal_testing/` and are **hidden** from Import History and analysis pickers. Do not use these for customer-facing demos.

## Small starter datasets

Friendly starter files (from `data/sample/`) appear as **Demo Sales Dataset**, **Demo Products Catalog**, and **Demo Inventory Dataset** when uploaded.
