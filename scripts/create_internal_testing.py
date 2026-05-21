#!/usr/bin/env python3
"""Create QA / broken datasets for internal testing (hidden from import UI)."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "internal_testing"
OUT.mkdir(parents=True, exist_ok=True)

# Broken: missing SKU column
pd.DataFrame({
    "order_id": ["O1", "O2"],
    "revenue": [100, 200],
    "quantity": [1, 2],
}).to_excel(OUT / "sales_missing_columns.xlsx", index=False)

# Broken: no sku on products
pd.DataFrame({
    "title": ["Ghost Product"],
    "price": [9.99],
    "category": ["Test"],
}).to_excel(OUT / "products_no_sku.xlsx", index=False)

# Empty inventory
pd.DataFrame(columns=["sku", "on_hand", "days_in_stock"]).to_excel(
    OUT / "inventory_empty.xlsx", index=False
)

# Confusing mixed headers
pd.DataFrame({
    "order_id": ["X1"],
    "product_name": ["Widget"],
    "sku": ["TST-1"],
    "revenue": [50],
    "on_hand": [5],
    "warehouse": ["WH1"],
    "price": [50],
}).to_excel(OUT / "mixed_headers_confuse.xlsx", index=False)

# Legacy valid names moved here for QA regression
legacy_sales = pd.DataFrame({
    "sku": ["SKU-001", "SKU-002"],
    "quantity": [1, 2],
    "revenue": [149.99, 69.98],
    "sold_at": ["2025-01-01", "2025-01-02"],
})
legacy_sales.to_excel(OUT / "sales_valid.xlsx", index=False)
pd.DataFrame({
    "sku": ["SKU-001"],
    "title": ["Test Product"],
    "category": ["Test"],
    "price": [10],
    "cost": [5],
}).to_excel(OUT / "products_valid.xlsx", index=False)
pd.DataFrame({
    "sku": ["SKU-001"],
    "quantity": [10],
    "days_in_stock": [30],
}).to_excel(OUT / "inventory_valid.xlsx", index=False)

print(f"Internal testing files written to {OUT}")
