#!/usr/bin/env python3
"""Generate enterprise-style demo XLSX packs for Nike, Apple, and Zara."""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "demo_companies"

random.seed(42)
np.random.seed(42)

COMPANIES = {
    "nike": {
        "sales_file": "sales_nike_q1_2025.xlsx",
        "products_file": "products_nike_catalog.xlsx",
        "inventory_file": "inventory_nike_warehouse.xlsx",
        "prefix": "NIKE",
        "currency": "USD",
        "regions": ["North America", "EMEA", "APAC", "LATAM"],
        "channels": ["Nike.com", "Nike App", "Wholesale", "Nike Retail", "Amazon", "Dick's Sporting Goods"],
        "categories": [
            ("Footwear", 0.38, (79, 220), (28, 95)),
            ("Apparel", 0.32, (35, 120), (12, 48)),
            ("Accessories", 0.18, (18, 65), (6, 28)),
            ("Equipment", 0.12, (25, 90), (9, 38)),
        ],
        "product_names": {
            "Footwear": ["Air Max Pulse", "Pegasus 41", "Dunk Low Retro", "Jordan 1 Mid", "Vomero 18", "Revolution 7"],
            "Apparel": ["Dri-FIT Legend Tee", "Tech Fleece Hoodie", "Pro Training Shorts", "Club Fleece Joggers"],
            "Accessories": ["Heritage Hip Pack", "Brasilia Backpack", "Swoosh Cap", "Everyday Cushion Socks 6pk"],
            "Equipment": ["Pitch Team Ball", "Court Lite Basketball", "Training Mat", "Resistance Bands Kit"],
        },
        "warehouses": ["WH-NA-MEM", "WH-EMEA-NL", "WH-APAC-SG"],
        "sales_rows": 12400,
        "product_count": 920,
    },
    "apple": {
        "sales_file": "sales_apple_store_q1_2025.xlsx",
        "products_file": "products_apple_catalog.xlsx",
        "inventory_file": "inventory_apple_warehouse.xlsx",
        "prefix": "AAPL",
        "currency": "USD",
        "regions": ["Americas", "Europe", "Greater China", "Japan", "Rest of Asia Pacific"],
        "channels": ["Apple Store", "Apple Online", "Best Buy", "Amazon", "Carrier Partners", "Education Store"],
        "categories": [
            ("iPhone", 0.34, (699, 1299), (420, 780)),
            ("Mac", 0.22, (999, 3499), (620, 2100)),
            ("iPad", 0.16, (349, 1299), (210, 720)),
            ("Watch", 0.14, (249, 849), (120, 410)),
            ("Accessories", 0.14, (19, 499), (8, 220)),
        ],
        "product_names": {
            "iPhone": ["iPhone 16 Pro", "iPhone 16", "iPhone 15", "iPhone SE"],
            "Mac": ["MacBook Air M3", "MacBook Pro 14\"", "iMac 24\"", "Mac mini M2"],
            "iPad": ["iPad Pro 13\"", "iPad Air", "iPad mini", "iPad 10th Gen"],
            "Watch": ["Apple Watch Series 10", "Apple Watch SE", "Apple Watch Ultra 2"],
            "Accessories": ["MagSafe Charger", "AirPods Pro 2", "USB-C Cable 2m", "Smart Folio"],
        },
        "warehouses": ["DC-CUPERTINO", "DC-SHAIGHAI", "DC-CORK"],
        "sales_rows": 9800,
        "product_count": 640,
    },
    "zara": {
        "sales_file": "sales_zara_global_q1_2025.xlsx",
        "products_file": "products_zara_catalog.xlsx",
        "inventory_file": "inventory_zara_warehouse.xlsx",
        "prefix": "ZARA",
        "currency": "EUR",
        "regions": ["Spain", "France", "UK", "Germany", "US", "UAE", "Mexico"],
        "channels": ["Zara.com", "Zara App", "Flagship Stores", "Zara Home", "Franchise", "ASOS Marketplace"],
        "categories": [
            ("Women", 0.36, (19, 129), (6, 42)),
            ("Men", 0.28, (25, 149), (8, 48)),
            ("Kids", 0.18, (12, 79), (4, 28)),
            ("TRF", 0.10, (15, 59), (5, 22)),
            ("Home", 0.08, (9, 89), (3, 35)),
        ],
        "product_names": {
            "Women": ["Satin Midi Dress", "Oversized Blazer", "Wide Leg Trousers", "Rib Knit Top"],
            "Men": ["Relaxed Fit Jeans", "Bomber Jacket", "Oxford Shirt", "Cargo Trousers"],
            "Kids": ["Printed Sweatshirt", "Denim Jacket Kids", "School Trousers"],
            "TRF": ["Crop Tank", "Baggy Jeans TRF", "Basic Tee 2-Pack"],
            "Home": ["Linen Cushion Cover", "Scented Candle", "Ceramic Vase"],
        },
        "warehouses": ["ES-ARTEIXO", "PL-LODZ", "CN-SHANGHAI"],
        "sales_rows": 11200,
        "product_count": 1180,
    },
}

CUSTOMERS = [
    "alex.morgan@email.com", "priya.sharma@email.com", "james.okonkwo@email.com",
    "maria.gonzalez@email.com", "chen.wei@email.com", "sophie.martin@email.com",
    "liam.brooks@email.com", "fatima.hassan@email.com", "noah.kim@email.com",
    "emma.wilson@email.com", "diego.santos@email.com", "yuki.tanaka@email.com",
]


def _pick_category(cfg: dict) -> tuple[str, float, tuple, tuple]:
    cats = cfg["categories"]
    r = random.random()
    acc = 0.0
    for cat, weight, price_rng, cost_rng in cats:
        acc += weight
        if r <= acc:
            return cat, weight, price_rng, cost_rng
    return cats[-1][0], cats[-1][1], cats[-1][2], cats[-1][3]


def build_products(cfg: dict) -> pd.DataFrame:
    prefix = cfg["prefix"]
    rows = []
    statuses = ["active", "active", "active", "active", "draft", "archived", "clearance"]
    n = cfg["product_count"]
    for i in range(1, n + 1):
        cat, _, price_rng, cost_rng = _pick_category(cfg)
        base_names = cfg["product_names"].get(cat, ["Essential Item"])
        variant = random.choice(["Black", "White", "Navy", "Olive", "Red", "Grey", "S", "M", "L", "XL", "42", "44"])
        title = f"{random.choice(base_names)} — {variant}"
        price = round(random.uniform(*price_rng), 2)
        # Low-margin / clearance scenarios
        if i % 47 == 0:
            cost = round(price * random.uniform(0.82, 0.94), 2)
            status = "clearance"
        elif i % 31 == 0:
            cost = round(price * random.uniform(0.75, 0.88), 2)
            status = "active"
        else:
            cost = round(random.uniform(*cost_rng), 2)
            status = random.choice(statuses)
        margin_pct = round((price - cost) / price * 100, 2) if price else 0
        discount_pct = round(random.choice([0, 0, 0, 5, 10, 15, 20, 25, 30]), 1)
        if status == "clearance":
            discount_pct = max(discount_pct, random.choice([25, 30, 40, 50]))
        compare = round(price * (1 + random.uniform(0.05, 0.25)), 2) if discount_pct else None
        launch = datetime(2023, 1, 1) + timedelta(days=random.randint(0, 800))
        rows.append({
            "sku": f"{prefix}-{i:04d}",
            "title": title,
            "category": cat,
            "price": price,
            "cost": cost,
            "compare_at_price": compare,
            "vendor": cfg["prefix"].title(),
            "status": status,
            "margin": margin_pct,
            "discount_pct": discount_pct,
            "currency": cfg["currency"],
            "launch_date": launch.strftime("%Y-%m-%d"),
        })
    return pd.DataFrame(rows)


def build_inventory(products: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    rows = []
    whs = cfg["warehouses"]
    for _, p in products.iterrows():
        sku = p["sku"]
        price = p["price"]
        # Dead / overstock / stockout patterns
        idx = int(sku.split("-")[-1])
        if idx % 53 == 0:
            on_hand, reserved, inbound, days = 0, 0, random.randint(20, 80), random.randint(120, 200)
            risk, turnover, days_rem = "critical", 0.0, 0
        elif idx % 41 == 0:
            on_hand = random.randint(400, 900)
            reserved = random.randint(10, 40)
            inbound = random.randint(0, 20)
            days = random.randint(150, 220)
            risk, turnover, days_rem = "low", round(random.uniform(0.2, 0.6), 2), random.randint(90, 180)
        elif idx % 29 == 0:
            on_hand = random.randint(2, 8)
            reserved = random.randint(1, 4)
            inbound = random.randint(15, 60)
            days = random.randint(8, 25)
            risk, turnover, days_rem = "high", round(random.uniform(4, 9), 2), random.randint(3, 12)
        else:
            on_hand = max(0, int(np.random.lognormal(3.2, 0.9)))
            reserved = min(on_hand, random.randint(0, max(1, on_hand // 4)))
            inbound = random.randint(0, max(0, 40 - on_hand // 10))
            days = random.randint(5, 90)
            turnover = round(random.uniform(1.5, 8.0), 2)
            if on_hand <= 5:
                risk = "high"
                days_rem = random.randint(2, 14)
            elif on_hand > 300:
                risk = "medium"
                days_rem = random.randint(60, 120)
            else:
                risk = "low"
                days_rem = random.randint(15, 75)
        available = max(0, on_hand - reserved)
        rows.append({
            "sku": sku,
            "warehouse": random.choice(whs),
            "on_hand": on_hand,
            "reserved": reserved,
            "inbound": inbound,
            "available_units": available,
            "days_in_stock": days,
            "inventory_turnover": turnover if idx % 53 != 0 else 0.0,
            "stockout_risk": risk,
            "days_remaining": days_rem,
            "currency": cfg["currency"],
            "unit_value": price,
        })
    return pd.DataFrame(rows)


def build_sales(products: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    skus = products["sku"].tolist()
    prices = dict(zip(products["sku"], products["price"]))
    costs = dict(zip(products["sku"], products["cost"]))
    weights = []
    for sku in skus:
        idx = int(sku.split("-")[-1])
        if idx % 17 == 0:
            weights.append(8.0)
        elif idx % 23 == 0:
            weights.append(0.15)
        else:
            weights.append(1.0)
    weights = np.array(weights) / sum(weights)

    start = datetime(2025, 1, 1)
    end = datetime(2025, 3, 31, 23, 59, 59)
    rows = []
    order_seq = 100000
    for _ in range(cfg["sales_rows"]):
        sku = random.choices(skus, weights=weights, k=1)[0]
        price = prices[sku]
        cost = costs[sku]
        qty = int(np.random.choice([1, 1, 1, 2, 2, 3], p=[0.45, 0.2, 0.1, 0.12, 0.08, 0.05]))
        # Seasonal spikes: late Jan (launch), mid Feb (Valentine's), late Mar (spring)
        day_offset = random.randint(0, 89)
        sold = start + timedelta(days=day_offset, hours=random.randint(8, 21), minutes=random.randint(0, 59))
        if 20 <= day_offset <= 28:
            qty = max(qty, random.randint(2, 5))
        if 44 <= day_offset <= 50:
            qty = max(qty, random.randint(1, 4))
        if 75 <= day_offset <= 89:
            qty = max(qty, random.randint(2, 6))

        discount = 0.0
        if random.random() < 0.18:
            discount = round(price * qty * random.uniform(0.05, 0.35), 2)
        if random.random() < 0.04:
            discount = round(price * qty * random.uniform(0.4, 0.65), 2)  # profit leakage

        revenue = round(price * qty - discount, 2)
        unit_price = price
        margin = round(revenue - cost * qty, 2)
        order_seq += 1
        rows.append({
            "order_id": f"ORD-{cfg['prefix']}-{order_seq}",
            "sku": sku,
            "quantity": qty,
            "unit_price": unit_price,
            "revenue": revenue,
            "margin": margin,
            "sales_channel": random.choice(cfg["channels"]),
            "sold_at": sold.strftime("%Y-%m-%d %H:%M:%S"),
            "region": random.choice(cfg["regions"]),
            "discount_amount": discount,
            "customer": random.choice(CUSTOMERS),
            "currency": cfg["currency"],
        })
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for key, cfg in COMPANIES.items():
        print(f"Generating {key}...")
        products = build_products(cfg)
        inventory = build_inventory(products, cfg)
        sales = build_sales(products, cfg)
        sales_skus = set(sales["sku"])
        inv_skus = set(inventory["sku"])
        prod_skus = set(products["sku"])
        assert sales_skus <= prod_skus, f"{key}: sales SKU mismatch"
        assert inv_skus == prod_skus, f"{key}: inventory SKU mismatch"

        products.to_excel(OUT / cfg["products_file"], index=False, engine="openpyxl")
        sales.to_excel(OUT / cfg["sales_file"], index=False, engine="openpyxl")
        inventory.to_excel(OUT / cfg["inventory_file"], index=False, engine="openpyxl")
        print(f"  products={len(products)}, sales={len(sales)}, inventory={len(inventory)}")

    print(f"Done. Files written to {OUT}")


if __name__ == "__main__":
    main()
