#!/usr/bin/env python3
"""Generate DriveLine Motor Parts demo pack (~100 products, ~3.8k sales)."""

from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "demo_companies"

random.seed(3030)

MOTOR = {
    "products_file": "motor_products.xlsx",
    "inventory_file": "motor_inventory.xlsx",
    "sales_file": "motor_sales_2025.xlsx",
    "product_count": 100,
    "sales_rows": 3_800,
}

BRANDS = ["DriveLine", "TorqueMax", "EuroParts", "ProStop", "VoltEdge"]
CATEGORIES = ["Lighting", "Brakes", "Electrical", "Suspension", "Filters"]
WAREHOUSES = ["Sarajevo DC", "Belgrade Hub", "Munich 3PL"]
CHANNELS = ["Web Store", "B2B Portal", "Marketplace", "Retail POS"]
REGIONS = ["BA", "HR", "RS", "DE", "AT"]
START = datetime(2025, 1, 1)


def build_products() -> pd.DataFrame:
    rows = []
    for i in range(1, MOTOR["product_count"] + 1):
        brand = BRANDS[i % len(BRANDS)]
        cat = CATEGORIES[i % len(CATEGORIES)]
        sku = f"MTR-{i:04d}"
        cost = round(random.uniform(8, 220), 2)
        price = round(cost * random.uniform(1.4, 2.2), 2)
        margin = round((price - cost) / price * 100, 2)
        rows.append(
            {
                "sku": sku,
                "title": f"{brand} {cat} Part {i:03d}",
                "category": cat,
                "brand": brand,
                "price": price,
                "cost": cost,
                "margin_pct": margin,
                "status": random.choice(["active", "active", "active", "clearance"]),
                "discount_pct": random.choice([0, 0, 5, 10]),
                "currency": "EUR",
                "launch_date": (START - timedelta(days=random.randint(30, 800))).strftime("%Y-%m-%d"),
            }
        )
    return pd.DataFrame(rows)


def build_inventory(products: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, p in products.iterrows():
        for wh in random.sample(WAREHOUSES, k=random.randint(1, 2)):
            on_hand = random.randint(0, 220)
            reserved = random.randint(0, min(30, on_hand))
            inbound = random.randint(0, 50)
            rows.append(
                {
                    "sku": p["sku"],
                    "warehouse": wh,
                    "on_hand": on_hand,
                    "reserved": reserved,
                    "inbound": inbound,
                    "available_units": max(0, on_hand - reserved),
                    "days_in_stock": random.randint(5, 200),
                    "turnover_90d": round(random.uniform(0.2, 5.0), 2),
                    "stockout_risk": random.choice(["low", "medium", "high"]),
                }
            )
    return pd.DataFrame(rows)


def build_sales(products: pd.DataFrame) -> pd.DataFrame:
    skus = products["sku"].tolist()
    price_map = dict(zip(products["sku"], products["price"]))
    cost_map = dict(zip(products["sku"], products["cost"]))
    rows = []
    order_seq = 20000
    for _ in range(MOTOR["sales_rows"]):
        order_seq += 1
        sku = random.choice(skus)
        qty = random.randint(1, 4)
        unit_price = price_map[sku] * random.uniform(0.88, 1.0)
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
                "customer": f"customer{random.randint(1, 900)}@example.com",
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("Generating DriveLine Motor Parts demo datasets...")
    products = build_products()
    inventory = build_inventory(products)
    sales = build_sales(products)

    products.to_excel(OUT / MOTOR["products_file"], index=False)
    inventory.to_excel(OUT / MOTOR["inventory_file"], index=False)
    sales.to_excel(OUT / MOTOR["sales_file"], index=False)

    print(f"  {MOTOR['products_file']}: {len(products):,} rows")
    print(f"  {MOTOR['inventory_file']}: {len(inventory):,} rows")
    print(f"  {MOTOR['sales_file']}: {len(sales):,} rows")
    print(f"  revenue ~${sales['revenue'].sum():,.2f}")
    print(f"\nDone -> {OUT}")


if __name__ == "__main__":
    main()
