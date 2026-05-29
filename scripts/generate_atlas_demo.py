#!/usr/bin/env python3
"""Generate Atlas Retail Group enterprise stress-test demo datasets (~100k sales).

Operational mix is baked into SKU profiles (legacy, seasonal, discontinued, etc.)
so inventory risk KPIs emerge naturally from the analytics engine — never hardcoded.
"""
from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "demo_companies"
SNAPSHOT_PATH = OUT / "atlas_analytics_snapshot.json"

random.seed(2026)
np.random.seed(2026)

ATLAS = {
    "sales_file": "atlas_sales_q1_2026.xlsx",
    "products_file": "atlas_products.xlsx",
    "inventory_file": "atlas_inventory.xlsx",
    "prefix": "ATLS",
    "currency": "USD",
    "regions": [
        "North America",
        "EMEA",
        "APAC",
        "LATAM",
        "UK & Ireland",
        "DACH",
        "Nordics",
        "ANZ",
    ],
    "channels": [
        "Atlas.com",
        "Atlas B2B Portal",
        "Amazon Marketplace",
        "Wholesale Partners",
        "Flagship Stores",
        "Mobile App",
        "Enterprise Procurement",
    ],
    "warehouses": [
        "WH-US-DAL",
        "WH-US-NJ",
        "WH-EU-ROT",
        "WH-UK-MAN",
        "WH-APAC-SG",
    ],
    "suppliers": [
        "TechDist Global LLC",
        "Apex Supply Partners",
        "Meridian Components EU",
        "Pacific Merch Solutions",
        "NorthStar Fulfillment Co.",
        "Summit OEM Industries",
        "Vertex Logistics Group",
    ],
    "sales_rows": 100_000,
    "product_count": 3_200,
}

# Target SKU operational segments (sum = product_count)
SEGMENT_QUOTAS: dict[str, int] = {
    "healthy": 1_840,
    "slow_moving": 480,
    "overstock": 400,
    "dead": 160,
    "low_stock": 240,
    "stockout": 80,
}

CATALOG: dict[str, dict] = {
    "Consumer Electronics": {
        "weight": 0.22,
        "price": (49, 899),
        "cost": (22, 520),
        "lines": ["Atlas Pro", "Vertex", "Summit", "Meridian"],
        "items": [
            ("Wireless Noise-Cancelling Headphones", ["Graphite", "Silver", "Midnight"]),
            ("True Wireless Earbuds", ["Black", "White", "Sand"]),
            ("Portable Bluetooth Speaker", ["Charcoal", "Ocean Blue"]),
            ("4K Webcam with Auto-Framing", ["Slate"]),
            ("USB-C Docking Station 12-in-1", ["Space Gray"]),
            ("27\" QHD Monitor", ["165Hz IPS", "240Hz VA"]),
            ("Mechanical Keyboard", ["Tactile Brown", "Linear Red"]),
            ("Precision Wireless Mouse", ["Graphite", "Pearl"]),
        ],
    },
    "Smart Home & IoT": {
        "weight": 0.14,
        "price": (29, 349),
        "cost": (11, 185),
        "lines": ["Atlas Home", "Nova", "Meridian"],
        "items": [
            ("Smart Thermostat Hub", ["Wi-Fi 6", "Matter Ready"]),
            ("Video Doorbell Pro", ["Satin Nickel", "Matte Black"]),
            ("Indoor Security Camera", ["2K HDR", "Pan-Tilt"]),
            ("Smart Light Starter Kit", ["Warm White", "RGB"]),
            ("Air Quality Monitor", ["PM2.5 + VOC"]),
            ("Smart Plug 4-Pack", ["15A"]),
        ],
    },
    "Fashion & Apparel": {
        "weight": 0.18,
        "price": (24, 289),
        "cost": (8, 118),
        "lines": ["Atlas Studio", "Summit Collection", "Meridian Tailored"],
        "items": [
            ("Merino Wool Crew Sweater", ["Navy", "Camel", "Charcoal"]),
            ("Tailored Stretch Blazer", ["Midnight", "Stone"]),
            ("Premium Denim Jean", ["Indigo Raw", "Washed Black"]),
            ("Performance Polo", ["White", "Forest", "Burgundy"]),
            ("Water-Resistant Parka", ["Black", "Olive"]),
            ("Italian Leather Belt", ["Brown", "Black"]),
        ],
    },
    "Gaming & Entertainment": {
        "weight": 0.12,
        "price": (39, 649),
        "cost": (16, 310),
        "lines": ["Vertex Gaming", "Atlas Arena"],
        "items": [
            ("Ultra Gaming Headset", ["7.1 Surround", "Wireless"]),
            ("RGB Gaming Chair", ["Stealth", "Crimson"]),
            ("Pro Controller", ["PC + Console"]),
            ("Streaming Capture Card", ["4K60 HDR"]),
            ("Curved Gaming Monitor 34\"", ["144Hz Ultrawide"]),
            ("Mechanical Keypad", ["Hot-Swap"]),
        ],
    },
    "Office & Productivity": {
        "weight": 0.11,
        "price": (19, 499),
        "cost": (7, 245),
        "lines": ["Summit Office", "Atlas Workspace"],
        "items": [
            ("Ergonomic Executive Chair", ["Midnight Leather", "Mesh Graphite"]),
            ("Height-Adjust Standing Desk", ["72\" Walnut", "60\" White"]),
            ("Dual Monitor Arm", ["Gas Spring"]),
            ("Document Scanner", ["Duplex ADF"]),
            ("Conference Speakerphone", ["Teams Certified"]),
            ("Laptop Stand Aluminum", ["Silver"]),
        ],
    },
    "Home & Living": {
        "weight": 0.13,
        "price": (18, 399),
        "cost": (6, 175),
        "lines": ["Atlas Living", "Meridian Home"],
        "items": [
            ("Memory Foam Pillow Set", ["Cooling Gel", "Standard"]),
            ("Weighted Blanket", ["15 lb", "20 lb"]),
            ("Ceramic Cookware Set", ["10-Piece"]),
            ("Robot Vacuum", ["LiDAR Mapping"]),
            ("Air Purifier HEPA", ["Large Room"]),
            ("Modular Storage Cabinet", ["Oak Finish"]),
        ],
    },
    "Accessories & Wearables": {
        "weight": 0.10,
        "price": (15, 449),
        "cost": (5, 195),
        "lines": ["Atlas Wear", "Nova Fit"],
        "items": [
            ("Fitness Tracker Band", ["Graphite", "Rose Gold"]),
            ("Smartwatch Series X", ["GPS", "Cellular"]),
            ("Travel Backpack 30L", ["Black", "Sandstone"]),
            ("RFID Passport Wallet", ["Leather Black"]),
            ("MagSafe Phone Case", ["Clear", "Slate"]),
            ("Wireless Charging Pad", ["15W Fast"]),
        ],
    },
}

CUSTOMERS = [
    "alex.morgan@corp-mail.com",
    "priya.sharma@enterprise.io",
    "james.okonkwo@retail-group.com",
    "maria.gonzalez@commerce.net",
    "chen.wei@global-ops.cn",
    "sophie.martin@atlas-partners.fr",
    "liam.brooks@wholesale.co.uk",
    "fatima.hassan@merch.ae",
    "noah.kim@distribution.kr",
    "emma.wilson@procurement.com",
    "diego.santos@latam-retail.mx",
    "yuki.tanaka@supply.jp",
    "olivia.chen@b2b-atlas.com",
    "marcus.jensen@nordics-retail.dk",
    "isabella.rodriguez@enterprise.es",
]

SEGMENT_LIFECYCLE = {
    "dead": [
        ("discontinued", "Legacy SKU — end-of-life"),
        ("archived", "Discontinued catalog line"),
        ("clearance", "Seasonal closeout — prior year"),
    ],
    "slow_moving": [
        ("clearance", "Aging seasonal assortment"),
        ("active", "Low-demand size variant"),
        ("active", "Regional slow mover"),
    ],
    "overstock": [
        ("active", "Excess warehouse allocation"),
        ("active", "Bulk procurement remainder"),
        ("clearance", "Over-ordered seasonal buy"),
    ],
    "low_stock": [("active", "High-velocity core SKU")],
    "stockout": [("active", "Core SKU — replenishment delay")],
    "healthy": [("active", "Standard catalog")],
}


def _category_plan(n: int) -> list[tuple[str, tuple, tuple]]:
    cats = list(CATALOG.items())
    weights = [cfg["weight"] for _, cfg in cats]
    total = sum(weights)
    weights = [w / total for w in weights]
    chosen = np.random.choice(len(cats), size=n, p=weights)
    plan: list[tuple[str, tuple, tuple]] = []
    for idx in chosen:
        name, cfg = cats[idx]
        plan.append((name, cfg["price"], cfg["cost"]))
    return plan


def _assign_segments(n: int) -> list[str]:
    segments: list[str] = []
    for name, count in SEGMENT_QUOTAS.items():
        segments.extend([name] * count)
    if len(segments) < n:
        segments.extend(["healthy"] * (n - len(segments)))
    elif len(segments) > n:
        segments = segments[:n]
    random.shuffle(segments)
    return segments


def build_products(cfg: dict) -> pd.DataFrame:
    prefix = cfg["prefix"]
    n = cfg["product_count"]
    plan = _category_plan(n)
    segments = _assign_segments(n)
    rows: list[dict] = []

    for i, (cat, price_rng, cost_rng) in enumerate(plan, start=1):
        segment = segments[i - 1]
        cat_cfg = CATALOG[cat]
        line = random.choice(cat_cfg["lines"])
        item, variants = random.choice(cat_cfg["items"])
        variant = random.choice(variants)
        title = f"{line} {item} — {variant}"
        price = round(random.uniform(*price_rng), 2)

        lifecycle_status, lifecycle_note = random.choice(SEGMENT_LIFECYCLE[segment])
        if segment == "dead":
            cost = round(random.uniform(*cost_rng), 2)
            status = lifecycle_status
            discount_pct = random.choice([30, 40, 50, 60])
            title = f"[Legacy] {title}"
        elif segment == "slow_moving":
            cost = round(random.uniform(*cost_rng), 2)
            status = lifecycle_status
            discount_pct = random.choice([15, 20, 25, 30])
        elif segment == "overstock":
            cost = round(random.uniform(*cost_rng), 2)
            status = lifecycle_status
            discount_pct = random.choice([10, 15, 20])
        elif i % 31 == 0:
            cost = round(price * random.uniform(0.74, 0.88), 2)
            status = "active"
            discount_pct = random.choice([5, 10, 15])
        else:
            cost = round(random.uniform(*cost_rng), 2)
            status = lifecycle_status if segment == "healthy" else "active"
            discount_pct = round(random.choice([0, 0, 0, 5, 10, 15]), 1)

        margin_pct = round((price - cost) / price * 100, 2) if price else 0.0
        compare = round(price * (1 + random.uniform(0.05, 0.25)), 2) if discount_pct else None
        launch = datetime(2019, 3, 1) + timedelta(days=random.randint(0, 2500))
        if segment == "dead":
            launch = datetime(2018, 1, 1) + timedelta(days=random.randint(0, 1400))

        rows.append(
            {
                "sku": f"{prefix}-{i:05d}",
                "title": title,
                "category": cat,
                "price": price,
                "cost": cost,
                "compare_at_price": compare,
                "vendor": "Atlas Retail Group",
                "supplier": random.choice(cfg["suppliers"]),
                "status": status,
                "margin": margin_pct,
                "discount_pct": discount_pct,
                "currency": cfg["currency"],
                "launch_date": launch.strftime("%Y-%m-%d"),
                "operational_segment": segment,
                "lifecycle_note": lifecycle_note,
            }
        )

    return pd.DataFrame(rows)


def build_inventory(products: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    rows: list[dict] = []
    whs = cfg["warehouses"]

    for _, p in products.iterrows():
        sku = p["sku"]
        price = p["price"]
        segment = p.get("operational_segment", "healthy")

        if segment == "dead":
            on_hand = random.randint(85, 420)
            reserved = random.randint(0, min(12, on_hand // 8))
            inbound = 0
            days = random.randint(210, 480)
            turnover = 0.0
            risk = "critical"
            days_rem = random.randint(200, 400)
        elif segment == "slow_moving":
            on_hand = random.randint(45, 220)
            reserved = random.randint(2, min(20, on_hand // 5))
            inbound = random.randint(0, 15)
            days = random.randint(95, 175)
            turnover = round(random.uniform(0.2, 0.7), 2)
            risk = "medium"
            days_rem = random.randint(90, 160)
        elif segment == "overstock":
            on_hand = random.randint(520, 1450)
            reserved = random.randint(10, 45)
            inbound = random.randint(0, 20)
            days = random.randint(110, 200)
            turnover = round(random.uniform(0.25, 0.85), 2)
            risk = "medium"
            days_rem = random.randint(140, 280)
        elif segment == "low_stock":
            on_hand = random.randint(2, 11)
            reserved = random.randint(0, max(0, on_hand - 1))
            inbound = random.randint(35, 120)
            days = random.randint(8, 35)
            turnover = round(random.uniform(4.5, 12.0), 2)
            risk = "high"
            days_rem = random.randint(3, 12)
        elif segment == "stockout":
            on_hand, reserved, inbound = 0, 0, random.randint(40, 160)
            days = random.randint(12, 40)
            turnover = round(random.uniform(3.0, 8.0), 2)
            risk = "critical"
            days_rem = 0
        else:
            on_hand = max(8, int(np.random.lognormal(3.5, 0.75)))
            on_hand = min(on_hand, 280)
            reserved = min(on_hand, random.randint(0, max(1, on_hand // 5)))
            inbound = random.randint(0, max(0, 45 - on_hand // 15))
            days = random.randint(12, 75)
            turnover = round(random.uniform(2.0, 9.0), 2)
            risk = "low"
            days_rem = random.randint(20, 65)

        available = max(0, on_hand - reserved)
        rows.append(
            {
                "sku": sku,
                "warehouse": random.choice(whs),
                "on_hand": on_hand,
                "reserved": reserved,
                "inbound": inbound,
                "available_units": available,
                "days_in_stock": days,
                "inventory_turnover": turnover,
                "stockout_risk": risk,
                "days_remaining": days_rem,
                "currency": cfg["currency"],
                "unit_value": price,
                "operational_segment": segment,
            }
        )

    return pd.DataFrame(rows)


def _day_offsets_for_segment(segments: np.ndarray) -> np.ndarray:
    """Per-row sale day within Q1, tuned by operational segment."""
    n = len(segments)
    offsets = np.zeros(n, dtype=np.int32)
    rules: dict[str, tuple[int, int]] = {
        "stockout": (45, 90),
        "slow_moving": (0, 22),
        "overstock": (0, 90),
        "low_stock": (55, 90),
        "healthy": (0, 90),
    }
    for seg, (lo, hi) in rules.items():
        mask = segments == seg
        cnt = int(mask.sum())
        if cnt:
            offsets[mask] = np.random.randint(lo, hi + 1, size=cnt)
    return offsets


def build_sales(products: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Vectorized ~100k sales with segment-aware demand weights."""
    target = cfg["sales_rows"]
    start = datetime(2026, 1, 1)
    active = products[products["operational_segment"] != "dead"].copy().reset_index(drop=True)

    segment_weights = {
        "healthy": 1.0,
        "low_stock": 11.0,
        "overstock": 0.35,
        "slow_moving": 0.22,
        "stockout": 6.5,
    }
    category_boost = {
        "Consumer Electronics": 1.35,
        "Fashion & Apparel": 1.15,
        "Gaming & Entertainment": 1.1,
        "Accessories & Wearables": 1.05,
    }

    weights = np.array(
        [
            segment_weights.get(row["operational_segment"], 1.0)
            * category_boost.get(row["category"], 1.0)
            for _, row in active.iterrows()
        ],
        dtype=float,
    )
    weights /= weights.sum()
    chosen = active.iloc[np.random.choice(len(active), size=target, p=weights)].reset_index(drop=True)

    segments = chosen["operational_segment"].to_numpy()
    day_offset = _day_offsets_for_segment(segments)
    qty = np.random.choice([1, 1, 1, 2, 2, 3, 4], size=target, p=[0.42, 0.18, 0.1, 0.12, 0.08, 0.06, 0.04])
    healthy_mask = segments == "healthy"
    if healthy_mask.any():
        boost = np.random.random(healthy_mask.sum()) < 0.15
        qty[healthy_mask] = np.where(boost, np.random.randint(2, 6, healthy_mask.sum()), qty[healthy_mask])

    unit_prices = chosen["price"].to_numpy(dtype=float)
    unit_costs = chosen["cost"].to_numpy(dtype=float)
    discount = np.zeros(target)
    disc_mask = np.random.random(target) < 0.17
    discount[disc_mask] = np.round(
        unit_prices[disc_mask] * qty[disc_mask] * np.random.uniform(0.05, 0.32, disc_mask.sum()),
        2,
    )
    leak_mask = np.random.random(target) < 0.035
    discount[leak_mask] = np.round(
        unit_prices[leak_mask] * qty[leak_mask] * np.random.uniform(0.4, 0.68, leak_mask.sum()),
        2,
    )
    revenue = np.round(unit_prices * qty - discount, 2)
    margin = np.round(revenue - unit_costs * qty, 2)
    hours = np.random.randint(8, 22, size=target)
    minutes = np.random.randint(0, 60, size=target)
    sold_at = [
        (start + timedelta(days=int(d), hours=int(h), minutes=int(m))).strftime("%Y-%m-%d %H:%M:%S")
        for d, h, m in zip(day_offset, hours, minutes)
    ]

    n = target
    refund_roll = np.random.random(n)
    order_status = np.where(refund_roll < 0.042, "refunded", "completed")
    partial = (refund_roll >= 0.042) & (refund_roll < 0.058)
    order_status = np.where(partial, "partial_refund", order_status)

    return pd.DataFrame(
        {
            "order_id": [f"ORD-{cfg['prefix']}-{100000 + i}" for i in range(1, n + 1)],
            "sku": chosen["sku"].to_numpy(),
            "quantity": qty,
            "unit_price": unit_prices,
            "revenue": revenue,
            "margin": margin,
            "sales_channel": np.random.choice(cfg["channels"], size=n),
            "sold_at": sold_at,
            "region": np.random.choice(cfg["regions"], size=n),
            "discount_amount": discount,
            "customer": np.random.choice(CUSTOMERS, size=n),
            "currency": cfg["currency"],
            "order_status": order_status,
            "refund_amount": np.where(
                order_status == "refunded",
                revenue,
                np.where(
                    order_status == "partial_refund",
                    np.round(revenue * np.random.uniform(0.2, 0.6, size=n), 2),
                    0.0,
                ),
            ),
        }
    )


def _fmt_currency(value: float) -> str:
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:,.0f}"


def _fmt_pct(value: float) -> str:
    return f"{value:.1f}%"


def compute_analytics_snapshot(
    products: pd.DataFrame,
    inventory: pd.DataFrame,
    sales: pd.DataFrame,
) -> dict:
    """Run the same engines as production analysis (no DB, no hardcoded KPIs)."""
    from app.engines.inventory_risk import InventoryRiskEngine
    from app.engines.profit_leakage import ProfitLeakageEngine
    from app.services.metrics_engine import MetricsEngine
    from app.utils.chart_data_builder import top_category_breakdown
    from app.utils.inventory_classification import normalize_inventory_columns

    inventory_norm = normalize_inventory_columns(inventory)
    inv_raw = InventoryRiskEngine().analyze(inventory_norm, sales, products)
    profit = ProfitLeakageEngine().analyze(products, sales, inventory_norm)
    analysis = {
        "inventory_risk": {
            "summary": inv_raw["summary"],
            "alerts": inv_raw["alerts"],
            "risk_rows": inv_raw.get("risk_rows", []),
        },
        "profit_leakage": profit,
    }
    selection = {
        "products_import_id": 1,
        "sales_import_id": 2,
        "inventory_import_id": 3,
    }
    metrics_model, _traces = MetricsEngine.compute(
        products, sales, inventory_norm, analysis, selection
    )
    m = metrics_model.model_dump() if hasattr(metrics_model, "model_dump") else metrics_model.dict()

    revenue = float(pd.to_numeric(sales["revenue"], errors="coerce").fillna(0).sum())
    sales_dates = pd.to_datetime(sales["sold_at"], errors="coerce")
    daily = (
        sales.assign(date=sales_dates.dt.date.astype(str))
        .groupby("date", as_index=False)["revenue"]
        .sum()
        .sort_values("date")
    )
    trend_vals = daily["revenue"].tolist()
    max_trend = max(trend_vals) if trend_vals else 1.0
    trend_bars = [max(8, int(100 * v / max_trend)) for v in trend_vals[-12:]]

    cat_rev = (
        sales.merge(products[["sku", "category"]], on="sku", how="left")
        .groupby("category")["revenue"]
        .sum()
        .reset_index()
    )
    cat_rows = top_category_breakdown(
        [{"category": r["category"], "revenue": float(r["revenue"])} for _, r in cat_rev.iterrows()],
        limit=6,
    )
    total_cat = sum(r["revenue"] for r in cat_rows) or 1.0
    category_labels = {
        "Consumer Electronics": "Electronics",
        "Fashion & Apparel": "Fashion",
        "Home & Living": "Home & Living",
        "Gaming & Entertainment": "Gaming",
        "Office & Productivity": "Office",
        "Smart Home & IoT": "Smart Home",
        "Accessories & Wearables": "Accessories",
    }
    category_mix = [
        {
            "label": category_labels.get(str(r["category"]), str(r["category"])[:20]),
            "pct": round(float(r["revenue"]) / total_cat * 100),
        }
        for r in cat_rows
    ]

    inv_summary = inv_raw["summary"]
    risk_rows = inv_raw.get("risk_rows") or []
    stockout_n = sum(1 for r in risk_rows if r.get("classification") == "stockout_risk")
    inv_total = max(len(products), 1)
    low_n = int(inv_summary.get("healthy_count", 0) or 0)
    med_n = int(inv_summary.get("slow_moving_count", 0) or 0) + int(
        inv_summary.get("overstock_count", 0) or 0
    )
    crit_n = (
        int(inv_summary.get("dead_inventory_count", 0) or 0)
        + int(inv_summary.get("low_stock_count", 0) or 0)
        + stockout_n
    )
    inventory_risk = [
        {"label": "Low", "pct": round(low_n / inv_total * 100)},
        {"label": "Medium", "pct": round(med_n / inv_total * 100)},
        {"label": "Critical", "pct": round(crit_n / inv_total * 100)},
    ]

    alert_count = len(inv_raw.get("alerts", [])) + int(profit.get("issue_count", 0) or 0)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "revenue_raw": revenue,
        "metrics": m,
        "inventory_summary": inv_summary,
        "segment_counts": (
            products["operational_segment"].value_counts().to_dict()
            if "operational_segment" in products.columns
            else {}
        ),
        "preview": {
            "revenue": _fmt_currency(revenue),
            "grossMargin": _fmt_pct(float(m.get("gross_margin_pct") or 0)),
            "inventoryEfficiency": _fmt_pct(float(m.get("inventory_efficiency") or 0)),
            "riskScore": f"{float(m.get('operational_risk_score') or 0):.1f}",
            "deadInventory": _fmt_currency(float(inv_summary.get("dead_inventory_value") or 0)),
            "ordersAnalyzed": f"{len(sales):,}",
            "activeProducts": f"{len(products):,}",
            "operationalAlerts": f"{alert_count:,}",
            "revenueTrendBars": trend_bars,
            "categoryMix": category_mix,
            "inventoryRisk": inventory_risk,
        },
    }


def sync_landing_config(snapshot: dict) -> None:
    """Write landing/src/config.ts preview block from computed snapshot."""
    preview = snapshot["preview"]
    config_path = ROOT / "landing" / "src" / "config.ts"
    text = config_path.read_text(encoding="utf-8")
    start_marker = "export const PREVIEW_ANALYTICS = "
    end_marker = "} as const;"
    start = text.index(start_marker)
    end = text.index(end_marker, start) + len(end_marker)
    mix_lines = ",\n".join(
        f'    {{ label: "{c["label"]}", pct: {c["pct"]} }}' for c in preview["categoryMix"]
    )
    risk_lines = ",\n".join(
        f'    {{ label: "{r["label"]}", pct: {r["pct"]} }}' for r in preview["inventoryRisk"]
    )
    block = (
        "export const PREVIEW_ANALYTICS = {\n"
        f'  revenue: "{preview["revenue"]}",\n'
        f'  grossMargin: "{preview["grossMargin"]}",\n'
        f'  inventoryEfficiency: "{preview["inventoryEfficiency"]}",\n'
        f'  riskScore: "{preview["riskScore"]}",\n'
        f'  deadInventory: "{preview["deadInventory"]}",\n'
        f'  ordersAnalyzed: "{preview["ordersAnalyzed"]}",\n'
        f'  activeProducts: "{preview["activeProducts"]}",\n'
        f'  operationalAlerts: "{preview["operationalAlerts"]}",\n'
        f"  revenueTrendBars: {json.dumps(preview['revenueTrendBars'])},\n"
        f"  categoryMix: [\n{mix_lines},\n  ],\n"
        f"  inventoryRisk: [\n{risk_lines},\n  ],\n"
        "} as const;"
    )
    config_path.write_text(text[:start] + block + text[end:], encoding="utf-8")
    print(f"  synced landing preview -> {config_path.relative_to(ROOT)}")


def update_chart_fallbacks(snapshot: dict) -> None:
    """Align chart_data_builder demo fallbacks with latest Atlas snapshot."""
    path = ROOT / "app" / "utils" / "chart_data_builder.py"
    text = path.read_text(encoding="utf-8")
    preview = snapshot["preview"]
    inv = snapshot.get("inventory_summary", {})
    revenue = float(snapshot.get("revenue_raw") or 0)

    inv_counts = {
        "Low": int(inv.get("healthy_count", 0) or 0),
        "Medium": int(inv.get("slow_moving_count", 0) or 0)
        + int(inv.get("overstock_count", 0) or 0),
        "Critical": int(inv.get("dead_inventory_count", 0) or 0)
        + int(inv.get("low_stock_count", 0) or 0),
    }

    if "def _demo_revenue_trend()" in text:
        bars = preview.get("revenueTrendBars") or [80] * 12
        daily_avg = revenue / 90.0 if revenue else 690_000.0
        new_fn = (
            "def _demo_revenue_trend() -> list[dict]:\n"
            '    """Fallback revenue trend — synced from Atlas analytics snapshot."""\n'
            f"    daily_avg = {daily_avg}\n"
            f"    multipliers = {[round(b / 100, 2) for b in bars]}\n"
            "    return [\n"
            '        {"date": f"2026-01-{i + 1:02d}", "revenue": round(daily_avg * multipliers[i % len(multipliers)], 2)}\n'
            "        for i in range(len(multipliers))\n"
            "    ]\n"
        )
        import re

        text = re.sub(
            r"def _demo_revenue_trend\(\)[\s\S]*?(?=\ndef _demo_categories)",
            new_fn,
            text,
        )

    cat_lines = []
    for item in preview.get("categoryMix", []):
        rev_est = revenue * (item["pct"] / 100.0)
        cat_lines.append(
            f'        {{"category": "{item["label"]}", "revenue": {round(rev_est, 2)}}},'
        )
    if cat_lines:
        new_cat = (
            "def _demo_categories() -> list[dict]:\n"
            '    """Fallback categories — synced from Atlas analytics snapshot."""\n'
            "    return [\n" + "\n".join(cat_lines) + "\n    ]\n"
        )
        import re

        text = re.sub(
            r"def _demo_categories\(\)[\s\S]*?(?=\ndef _demo_inventory_risk)",
            new_cat,
            text,
        )

    new_inv = (
        "def _demo_inventory_risk() -> dict[str, int]:\n"
        '    """Fallback inventory risk — synced from Atlas analytics snapshot."""\n'
        f"    return {json.dumps(inv_counts)}\n"
    )
    import re

    text = re.sub(
        r"def _demo_inventory_risk\(\)[\s\S]*?(?=\ndef ensure_chart_payload)",
        new_inv,
        text,
    )
    path.write_text(text, encoding="utf-8")
    print(f"  synced chart fallbacks -> {path.relative_to(ROOT)}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = ATLAS
    print("Generating Atlas Retail Group enterprise datasets...")
    products = build_products(cfg)
    inventory = build_inventory(products, cfg)
    sales = build_sales(products, cfg)

    sales_skus = set(sales["sku"])
    inv_skus = set(inventory["sku"])
    prod_skus = set(products["sku"])
    assert sales_skus <= prod_skus, "Atlas: sales SKU mismatch"
    assert inv_skus == prod_skus, "Atlas: inventory SKU mismatch"
    assert len(sales) == cfg["sales_rows"], f"Expected {cfg['sales_rows']} sales rows, got {len(sales)}"

    products.to_excel(OUT / cfg["products_file"], index=False, engine="openpyxl")
    print(f"  wrote {cfg['products_file']} ({len(products):,} rows)")
    inventory.to_excel(OUT / cfg["inventory_file"], index=False, engine="openpyxl")
    print(f"  wrote {cfg['inventory_file']} ({len(inventory):,} rows)")
    sales.to_excel(OUT / cfg["sales_file"], index=False, engine="openpyxl")
    print(f"  wrote {cfg['sales_file']} ({len(sales):,} rows)")

    print("\nComputing analytics snapshot (production engines)...")
    snapshot = compute_analytics_snapshot(products, inventory, sales)
    SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")
    print(f"  wrote {SNAPSHOT_PATH.relative_to(ROOT)}")

    inv_s = snapshot["inventory_summary"]
    print(
        f"  dead inventory: {_fmt_currency(float(inv_s.get('dead_inventory_value') or 0))} "
        f"({inv_s.get('dead_inventory_count', 0)} SKUs)"
    )
    print(f"  slow moving: {inv_s.get('slow_moving_count', 0)} | overstock: {inv_s.get('overstock_count', 0)}")
    print(f"  healthy: {inv_s.get('healthy_count', 0)} | segments: {snapshot['segment_counts']}")

    sync_landing_config(snapshot)
    update_chart_fallbacks(snapshot)
    print(f"\nDone. Files written to {OUT}")


if __name__ == "__main__":
    main()
