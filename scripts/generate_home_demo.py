#!/usr/bin/env python3
"""Generate Aurora Home (white goods / appliances) demo pack (~110 products, ~3.6k sales)."""

from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "demo_companies"

random.seed(4040)

HOME = {
    "products_file": "home_products.xlsx",
    "inventory_file": "home_inventory.xlsx",
    "sales_file": "home_sales_2025.xlsx",
    "product_count": 110,
    "sales_rows": 3_600,
}

BRANDS = ["Aurora Home", "NordicLine", "PureKitchen", "CoolTech", "WashPro"]
CATEGORIES = ["Kitchen", "Laundry", "Cooling", "Climate", "Small Appliances"]
WAREHOUSES = ["Sarajevo DC", "Ljubljana Hub", "Vienna 3PL"]
CHANNELS = ["Web Store", "Retail Chain", "Marketplace", "B2B Installers"]
REGIONS = ["BA", "HR", "SI", "AT", "DE"]
START = datetime(2025, 1, 1)


def build_products() -> pd.DataFrame:
    rows = []
    for i in range(1, HOME["product_count"] + 1):
        brand = BRANDS[i % len(BRANDS)]
        cat = CATEGORIES[i % len(CATEGORIES)]
        sku = f"HAP-{i:04d}"
        cost = round(random.uniform(60, 890), 2)
        price = round(cost * random.uniform(1.25, 1.85), 2)
        margin = round((price - cost) / price * 100, 2)
        rows.append(
            {
                "sku": sku,
                "title": f"{brand} {cat} Appliance {i:03d}",
                "category": cat,
                "brand": brand,
                "price": price,
                "cost": cost,
                "margin_pct": margin,
                "status": random.choice(["active", "active", "active", "clearance"]),
                "discount_pct": random.choice([0, 0, 5, 12]),
                "currency": "EUR",
                "launch_date": (START - timedelta(days=random.randint(45, 700))).strftime("%Y-%m-%d"),
            }
        )
    return pd.DataFrame(rows)


def build_inventory(products: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, p in products.iterrows():
        for wh in random.sample(WAREHOUSES, k=random.randint(1, 2)):
            on_hand = random.randint(0, 95)
            reserved = random.randint(0, min(12, on_hand))
            inbound = random.randint(0, 25)
            rows.append(
                {
                    "sku": p["sku"],
                    "warehouse": wh,
                    "on_hand": on_hand,
                    "reserved": reserved,
                    "inbound": inbound,
                    "available_units": max(0, on_hand - reserved),
                    "days_in_stock": random.randint(8, 220),
                    "turnover_90d": round(random.uniform(0.15, 3.8), 2),
                    "stockout_risk": random.choice(["low", "medium", "high"]),
                }
            )
    return pd.DataFrame(rows)


def build_sales(products: pd.DataFrame) -> pd.DataFrame:
    skus = products["sku"].tolist()
    price_map = dict(zip(products["sku"], products["price"]))
    cost_map = dict(zip(products["sku"], products["cost"]))
    rows = []
    order_seq = 30000
    for _ in range(HOME["sales_rows"]):
        order_seq += 1
        sku = random.choice(skus)
        qty = random.randint(1, 2)
        unit_price = price_map[sku] * random.uniform(0.9, 1.0)
        revenue = round(unit_price * qty, 2)
        margin = round(revenue - cost_map[sku] * qty, 2)
        sold_at = START + timedelta(
            days=random.randint(0, 364),
            hours=random.randint(8, 20),
            minutes=random.randint(0, 59),
        )
        rows.append(
            {
                "order_id": f"ORD-{order_seq}",
                "sku": sku,
                "quantity": qty,
                "revenue": revenue,
                "margin": margin,
                "sales_channel": random.choice(CHANNELS),
                "sold_at": sold_at.strftime("%Y-%m-%d %H:%M"),
                "region": random.choice(REGIONS),
                "discount_amount": round(max(0, price_map[sku] * qty - revenue), 2),
                "customer": f"customer{random.randint(1, 1200)}@example.com",
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("Generating Aurora Home (appliances) demo datasets...")
    products = build_products()
    inventory = build_inventory(products)
    sales = build_sales(products)

    products.to_excel(OUT / HOME["products_file"], index=False)
    inventory.to_excel(OUT / HOME["inventory_file"], index=False)
    sales.to_excel(OUT / HOME["sales_file"], index=False)

    print(f"  {HOME['products_file']}: {len(products):,} rows")
    print(f"  {HOME['inventory_file']}: {len(inventory):,} rows")
    print(f"  {HOME['sales_file']}: {len(sales):,} rows")
    print(f"  revenue ~${sales['revenue'].sum():,.2f}")
    print(f"\nDone -> {OUT}")


if __name__ == "__main__":
    main()
