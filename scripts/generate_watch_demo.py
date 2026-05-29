#!/usr/bin/env python3
"""Generate ChronoHaus Watch Co. demo pack (~120 products, ~4.5k sales) for live guest workspace."""

from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "demo_companies"
SNAPSHOT_PATH = OUT / "watch_analytics_snapshot.json"

random.seed(2026)

WATCH = {
    "products_file": "watch_products.xlsx",
    "inventory_file": "watch_inventory.xlsx",
    "sales_file": "watch_sales_2025.xlsx",
    "product_count": 120,
    "sales_rows": 4_500,
}

BRANDS = ["ChronoHaus", "Nordvik", "Meridian", "Apex Time", "Velo Watch Co."]
CATEGORIES = ["Dress", "Sport", "Dive", "Pilot", "Smart Hybrid"]
WAREHOUSES = ["Zagreb DC", "Sarajevo Hub", "Munich 3PL"]
CHANNELS = ["Web Store", "Amazon EU", "Retail POS", "B2B Portal"]
REGIONS = ["BA", "HR", "DE", "AT", "SI"]
START = datetime(2025, 1, 1)


def build_products() -> pd.DataFrame:
    rows = []
    for i in range(1, WATCH["product_count"] + 1):
        brand = BRANDS[i % len(BRANDS)]
        cat = CATEGORIES[i % len(CATEGORIES)]
        sku = f"WCH-{i:04d}"
        cost = round(random.uniform(45, 420), 2)
        price = round(cost * random.uniform(1.35, 2.1), 2)
        margin = round((price - cost) / price * 100, 2)
        rows.append(
            {
                "sku": sku,
                "title": f"{brand} {cat} Watch {i:03d}",
                "category": cat,
                "brand": brand,
                "price": price,
                "cost": cost,
                "margin_pct": margin,
                "status": random.choice(["active", "active", "active", "clearance"]),
                "discount_pct": random.choice([0, 0, 5, 10, 15]),
                "currency": "EUR",
                "launch_date": (START - timedelta(days=random.randint(30, 900))).strftime("%Y-%m-%d"),
            }
        )
    return pd.DataFrame(rows)


def build_inventory(products: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, p in products.iterrows():
        for wh in random.sample(WAREHOUSES, k=random.randint(1, 2)):
            on_hand = random.randint(0, 180)
            reserved = random.randint(0, min(25, on_hand))
            inbound = random.randint(0, 40)
            rows.append(
                {
                    "sku": p["sku"],
                    "warehouse": wh,
                    "on_hand": on_hand,
                    "reserved": reserved,
                    "inbound": inbound,
                    "available_units": max(0, on_hand - reserved),
                    "days_in_stock": random.randint(5, 240),
                    "turnover_90d": round(random.uniform(0.1, 4.5), 2),
                    "stockout_risk": random.choice(["low", "medium", "high"]),
                }
            )
    return pd.DataFrame(rows)


def build_sales(products: pd.DataFrame) -> pd.DataFrame:
    skus = products["sku"].tolist()
    price_map = dict(zip(products["sku"], products["price"]))
    cost_map = dict(zip(products["sku"], products["cost"]))
    rows = []
    order_seq = 10000
    for _ in range(WATCH["sales_rows"]):
        order_seq += 1
        sku = random.choice(skus)
        qty = random.randint(1, 3)
        unit_price = price_map[sku] * random.uniform(0.85, 1.0)
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
                "customer": f"customer{random.randint(1, 850)}@example.com",
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    from scripts.generate_atlas_demo import (
        compute_analytics_snapshot,
        sync_landing_config,
        update_chart_fallbacks,
    )

    OUT.mkdir(parents=True, exist_ok=True)
    print("Generating ChronoHaus Watch Co. demo datasets...")
    products = build_products()
    inventory = build_inventory(products)
    sales = build_sales(products)

    assert set(sales["sku"]) <= set(products["sku"])
    assert set(inventory["sku"]) <= set(products["sku"])

    products.to_excel(OUT / WATCH["products_file"], index=False)
    inventory.to_excel(OUT / WATCH["inventory_file"], index=False)
    sales.to_excel(OUT / WATCH["sales_file"], index=False)
    print(f"  {WATCH['products_file']}: {len(products):,} rows")
    print(f"  {WATCH['inventory_file']}: {len(inventory):,} rows")
    print(f"  {WATCH['sales_file']}: {len(sales):,} rows")

    print("\nComputing analytics snapshot...")
    snapshot = compute_analytics_snapshot(products, inventory, sales)
    SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")
    sync_landing_config(snapshot)
    update_chart_fallbacks(snapshot)
    print(f"\nDone -> {OUT}")


if __name__ == "__main__":
    main()
